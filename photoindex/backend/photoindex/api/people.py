"""People, face groups, single faces and the review queue."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.db import session_factory
from photoindex.faces.people import refresher
from photoindex.models import Face, Person, Photo

router = APIRouter(prefix="/api")
SAMPLE = 12  # faces shown per group / per person card


def db() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


def face_json(f: Face, names: dict[int, str] | None = None) -> dict:
    names = names or {}
    return dict(
        id=f.id, photo_id=f.photo_id, box=[f.x, f.y, f.w, f.h], size_px=f.size_px, quality=f.quality,
        crop_url=storage.image_url(f.crop_key) if f.crop_key else None,
        person_id=f.person_id, person_name=names.get(f.person_id) if f.person_id else None,
        assigned_by=f.assigned_by, cluster_id=f.cluster_id, ignored=f.ignored,
        suggested_person_id=f.suggested_person_id, suggested_score=f.suggested_score,
        suggested_name=names.get(f.suggested_person_id) if f.suggested_person_id else None,
    )


def _names(session: Session) -> dict[int, str]:
    return dict(session.execute(select(Person.id, Person.name)).all())


def _person_by(session: Session, person_id: int | None, name: str | None) -> Person:
    """An existing person by id, or by name (created if new)."""
    if person_id is not None:
        p = session.get(Person, person_id)
        if p is None:
            raise HTTPException(404, "no such person")
        return p
    name = (name or "").strip()
    if not name:
        raise HTTPException(422, "person_id or name is required")
    p = session.scalar(select(Person).where(func.lower(Person.name) == name.lower()))
    if p is None:
        p = Person(name=name)
        session.add(p)
        session.flush()
    return p


def _assign(session: Session, face_ids: list[int], person: Person) -> None:
    """You said these faces are `person`: label them, and stop suggesting or grouping them."""
    session.execute(
        update(Face).where(Face.id.in_(face_ids)).values(
            person_id=person.id, assigned_by="user", suggested_person_id=None, suggested_score=None,
            cluster_id=None, ignored=False, rejected_person_ids=func.array_remove(Face.rejected_person_ids, person.id),
        )
    )


def _unassign(session: Session, face_ids: list[int]) -> None:
    """These faces are *not* who they were labelled as: remember that, so they aren't matched back."""
    session.execute(
        update(Face).where(Face.id.in_(face_ids), Face.person_id.is_not(None)).values(
            rejected_person_ids=func.array_append(Face.rejected_person_ids, Face.person_id),
        )
    )
    session.execute(update(Face).where(Face.id.in_(face_ids)).values(
        person_id=None, assigned_by=None, suggested_person_id=None, suggested_score=None))


# --- People --------------------------------------------------------------------------------------------------


def person_json(session: Session, p: Person, counts: dict[int, tuple[int, int]]) -> dict:
    faces, photos = counts.get(p.id, (0, 0))
    cover = session.get(Face, p.cover_face_id) if p.cover_face_id else None
    if cover is None or cover.person_id != p.id:
        cover = session.scalar(select(Face).where(Face.person_id == p.id).order_by(Face.quality.desc()).limit(1))
    return dict(id=p.id, name=p.name, faces=faces, photos=photos, cover_face_id=cover.id if cover else None,
                cover_url=storage.image_url(cover.crop_key) if cover and cover.crop_key else None)


def _counts(session: Session) -> dict[int, tuple[int, int]]:
    rows = session.execute(
        select(Face.person_id, func.count(), func.count(func.distinct(Face.photo_id)))
        .where(Face.person_id.is_not(None), ~Face.ignored).group_by(Face.person_id)
    ).all()
    return {pid: (n, photos) for pid, n, photos in rows}


@router.get("/people")
def list_people(session: Session = Depends(db)) -> list[dict]:
    counts = _counts(session)
    people = session.scalars(select(Person)).all()
    return sorted((person_json(session, p, counts) for p in people), key=lambda p: (-p["photos"], p["name"]))


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cover_face_id: int | None = None


@router.post("/people", status_code=201)
def create_person(body: PersonIn, session: Session = Depends(db)) -> dict:
    p = _person_by(session, None, body.name)
    session.commit()
    return person_json(session, p, _counts(session))


@router.get("/people/{person_id}")
def get_person(person_id: int, session: Session = Depends(db)) -> dict:
    p = session.get(Person, person_id)
    if p is None:
        raise HTTPException(404)
    return person_json(session, p, _counts(session))


@router.put("/people/{person_id}")
def update_person(person_id: int, body: PersonIn, session: Session = Depends(db)) -> dict:
    p = session.get(Person, person_id)
    if p is None:
        raise HTTPException(404)
    p.name = body.name.strip()
    p.cover_face_id = body.cover_face_id
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"someone named '{body.name}' already exists; merge instead")
    return person_json(session, p, _counts(session))


@router.delete("/people/{person_id}", status_code=204)
def delete_person(person_id: int, session: Session = Depends(db)) -> None:
    """Forget a person. Their faces become unnamed again (and regroup on the next pipeline run)."""
    p = session.get(Person, person_id)
    if p is None:
        raise HTTPException(404)
    session.execute(update(Face).where(Face.person_id == person_id).values(person_id=None, assigned_by=None))
    session.execute(update(Face).values(rejected_person_ids=func.array_remove(Face.rejected_person_ids, person_id)))
    session.delete(p)
    session.commit()
    refresher.request()


class MergeIn(BaseModel):
    into_id: int


@router.post("/people/{person_id}/merge")
def merge_person(person_id: int, body: MergeIn, session: Session = Depends(db)) -> dict:
    """Two people are one (e.g. the same kid as a toddler and as a teenager): move every face over."""
    src, dst = session.get(Person, person_id), session.get(Person, body.into_id)
    if src is None or dst is None or src.id == dst.id:
        raise HTTPException(422, "need two different people")
    session.execute(update(Face).where(Face.person_id == src.id).values(person_id=dst.id))
    session.execute(update(Face).where(Face.suggested_person_id == src.id).values(suggested_person_id=dst.id))
    session.execute(update(Face).values(
        rejected_person_ids=func.array_replace(Face.rejected_person_ids, src.id, dst.id)))
    session.delete(src)
    session.commit()
    refresher.request()
    return person_json(session, dst, _counts(session))


@router.get("/people/{person_id}/faces")
def person_faces(person_id: int, offset: int = 0, limit: int = Query(200, le=1000),
                 session: Session = Depends(db)) -> dict:
    taken = func.coalesce(Photo.taken_at, Photo.client_modified)
    rows = session.scalars(
        select(Face).join(Photo, Photo.id == Face.photo_id).where(Face.person_id == person_id, ~Face.ignored)
        .order_by(taken.asc().nulls_last(), Face.id).offset(offset).limit(limit + 1)
    ).all()
    names = _names(session)
    return dict(faces=[face_json(f, names) for f in rows[:limit]], has_more=len(rows) > limit)


# --- Groups of unnamed faces ---------------------------------------------------------------------------------


@router.get("/clusters")
def list_clusters(offset: int = 0, limit: int = Query(20, le=100), session: Session = Depends(db)) -> dict:
    """Groups of similar unnamed faces, biggest first, each with its best-quality faces."""
    unnamed = (Face.person_id.is_(None), ~Face.ignored)
    sizes = session.execute(
        select(Face.cluster_id, func.count().label("n")).where(*unnamed, Face.cluster_id.is_not(None))
        .group_by(Face.cluster_id).order_by(func.count().desc(), Face.cluster_id).offset(offset).limit(limit + 1)
    ).all()
    out = []
    for cid, n in sizes[:limit]:
        faces = session.scalars(
            select(Face).where(*unnamed, Face.cluster_id == cid).order_by(Face.quality.desc()).limit(SAMPLE)
        ).all()
        out.append(dict(cluster_id=cid, size=n, faces=[face_json(f) for f in faces]))
    totals = session.execute(select(
        func.count(func.distinct(Face.cluster_id)), func.count().filter(Face.cluster_id.is_(None)),
    ).where(*unnamed)).one()
    return dict(clusters=out, has_more=len(sizes) > limit, groups=totals[0], ungrouped=totals[1])


@router.get("/clusters/{cluster_id}/faces")
def cluster_faces(cluster_id: int, session: Session = Depends(db)) -> list[dict]:
    rows = session.scalars(
        select(Face).where(Face.cluster_id == cluster_id, Face.person_id.is_(None), ~Face.ignored)
        .order_by(Face.quality.desc())
    ).all()
    return [face_json(f) for f in rows]


class ClusterAssignIn(BaseModel):
    person_id: int | None = None
    name: str | None = None
    exclude_face_ids: list[int] = Field(default_factory=list)  # faces in the group that aren't this person


def _cluster_members(session: Session, cluster_id: int, exclude: list[int]) -> list[int]:
    ids = list(session.scalars(select(Face.id).where(
        Face.cluster_id == cluster_id, Face.person_id.is_(None), ~Face.ignored)))
    if not ids:
        raise HTTPException(404, "no such group (it may have been regrouped; reload)")
    if exclude:  # pulled out of the group, so they don't get swept up with it
        session.execute(update(Face).where(Face.id.in_(exclude), Face.cluster_id == cluster_id).values(cluster_id=None))
    return [i for i in ids if i not in set(exclude)]


@router.post("/clusters/{cluster_id}/assign")
def assign_cluster(cluster_id: int, body: ClusterAssignIn, session: Session = Depends(db)) -> dict:
    members = _cluster_members(session, cluster_id, body.exclude_face_ids)
    person = _person_by(session, body.person_id, body.name)
    _assign(session, members, person)
    if body.exclude_face_ids:  # you said these aren't `person`, so don't match them back to them
        session.execute(update(Face).where(Face.id.in_(body.exclude_face_ids)).values(
            rejected_person_ids=func.array_append(Face.rejected_person_ids, person.id)))
    session.commit()
    refresher.request()
    return person_json(session, person, _counts(session))


@router.post("/clusters/{cluster_id}/ignore")
def ignore_cluster(cluster_id: int, body: ClusterAssignIn, session: Session = Depends(db)) -> dict:
    """Not someone you care about (strangers, crowds): hide these faces from groups and suggestions."""
    members = _cluster_members(session, cluster_id, body.exclude_face_ids)
    session.execute(update(Face).where(Face.id.in_(members)).values(ignored=True, cluster_id=None))
    session.commit()
    return dict(ignored=len(members))


@router.post("/clusters/regroup", status_code=202)
def regroup() -> dict:
    """Regroup the unnamed faces in the background (the pipeline also does this after finding new faces)."""
    refresher.request(regroup=True)
    return dict(started=True)


# --- Single faces --------------------------------------------------------------------------------------------


@router.get("/photos/{photo_id}/faces")
def photo_faces(photo_id: int, session: Session = Depends(db)) -> list[dict]:
    names = _names(session)
    rows = session.scalars(select(Face).where(Face.photo_id == photo_id).order_by(Face.x)).all()
    return [face_json(f, names) for f in rows]


class FaceIn(BaseModel):
    person_id: int | None = None
    name: str | None = None  # assign to this person (created if new)
    clear: bool = False  # not the person it's labelled as
    ignored: bool | None = None  # not someone you care about


@router.patch("/faces/{face_id}")
def update_face(face_id: int, body: FaceIn, session: Session = Depends(db)) -> dict:
    f = session.get(Face, face_id)
    if f is None:
        raise HTTPException(404)
    if body.person_id is not None or (body.name or "").strip():
        _assign(session, [f.id], _person_by(session, body.person_id, body.name))
    elif body.clear:
        _unassign(session, [f.id])
    if body.ignored is not None:
        session.execute(update(Face).where(Face.id == f.id).values(
            ignored=body.ignored, **(dict(person_id=None, assigned_by=None, cluster_id=None) if body.ignored else {})))
    session.commit()
    refresher.request()
    session.refresh(f)
    return face_json(f, _names(session))


# --- Review queue --------------------------------------------------------------------------------------------


@router.get("/review")
def review_queue(limit: int = Query(20, le=100), session: Session = Depends(db)) -> dict:
    """Uncertain matches, most likely first, each with a few confirmed faces of the suggested person."""
    names = _names(session)
    pending = (Face.suggested_person_id.is_not(None), Face.person_id.is_(None), ~Face.ignored)
    rows = session.scalars(select(Face).where(*pending).order_by(Face.suggested_score.desc(), Face.id).limit(limit)).all()
    examples: dict[int, list[dict]] = {}
    for pid in {f.suggested_person_id for f in rows}:
        examples[pid] = [face_json(e) for e in session.scalars(
            select(Face).where(Face.person_id == pid, Face.assigned_by == "user")
            .order_by(Face.quality.desc()).limit(4))]
    total = session.scalar(select(func.count()).where(*pending))
    out = []
    for f in rows:
        photo = session.get(Photo, f.photo_id)
        out.append(face_json(f, names) | dict(
            examples=examples.get(f.suggested_person_id, []),
            photo_thumb_url=storage.image_url(photo.thumb_key) if photo and photo.thumb_key else None,
        ))
    return dict(faces=out, total=total)


class ReviewIn(BaseModel):
    accept: bool


@router.post("/faces/{face_id}/review")
def review_face(face_id: int, body: ReviewIn, session: Session = Depends(db)) -> dict:
    f = session.get(Face, face_id)
    if f is None or f.suggested_person_id is None:
        raise HTTPException(409, "no suggestion for this face any more")
    if body.accept:
        _assign(session, [f.id], session.get(Person, f.suggested_person_id))
    else:
        session.execute(update(Face).where(Face.id == f.id).values(
            rejected_person_ids=func.array_append(Face.rejected_person_ids, f.suggested_person_id),
            suggested_person_id=None, suggested_score=None))
    session.commit()
    refresher.request()
    return dict(ok=True)


@router.get("/faces/stats")
def face_stats(session: Session = Depends(db)) -> dict:
    row = session.execute(select(
        func.count(),
        func.count().filter(Face.assigned_by == "user"),
        func.count().filter(Face.assigned_by == "auto"),
        func.count().filter(Face.suggested_person_id.is_not(None), Face.person_id.is_(None), ~Face.ignored),
        func.count().filter(Face.person_id.is_(None), ~Face.ignored),
        func.count().filter(Face.ignored),
    )).one()
    return dict(faces=row[0], named_by_you=row[1], named_auto=row[2], to_review=row[3], unnamed=row[4],
                ignored=row[5], people=session.scalar(select(func.count()).select_from(Person)),
                updating=refresher.busy)
