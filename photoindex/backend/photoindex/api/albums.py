"""The scanned print albums: events, reference sets (places and occasions) and naming childhood faces."""

from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.albums.faces import rematch
from photoindex.albums.names import order_key, page_of
from photoindex.albums.refs import group_faces
from photoindex.db import session_factory
from photoindex.models import AlbumEvent, AlbumFace, AlbumRef, AlbumRefExample, Person, Photo

router = APIRouter(prefix="/api/albums")


def db() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


@router.get("")
def albums(album: str | None = Query(None), session: Session = Depends(db)) -> dict:
    folder = func.substring(Photo.parent_path_lower, "[^/]+$")  # the album folder's name
    summary = [dict(album=a, prints=n, faces_done=done, events=0, events_with_me=0) for a, n, done in session.execute(
        select(folder, func.count(), func.count().filter(Photo.face_status == "done"))
        .where(Photo.album_scan, ~Photo.deleted).group_by(folder).order_by(folder)
    )]
    by_album = {s["album"]: s for s in summary}
    for a, n, me in session.execute(
        select(AlbumEvent.album, func.count(), func.count().filter(AlbumEvent.has_me)).group_by(AlbumEvent.album)
    ):
        if a in by_album:
            by_album[a].update(events=n, events_with_me=me)
    album = album or (summary[0]["album"] if summary else None)

    events = session.scalars(select(AlbumEvent).where(AlbumEvent.album == album).order_by(AlbumEvent.seq)).all()
    photos = defaultdict(list)
    for p in session.execute(
        select(Photo.id, Photo.name, Photo.thumb_key, Photo.album_event_id, Photo.face_count)
        .where(Photo.album_event_id.in_([e.id for e in events]))
    ):
        photos[p.album_event_id].append(p)
    names = dict(session.execute(select(Person.id, Person.name)).all())
    faces = session.scalar(select(func.count()).select_from(AlbumFace))
    return dict(
        albums=summary, album=album, faces=faces,
        events=[dict(
            id=e.id, seq=e.seq, size=e.size, first_name=e.first_name, last_name=e.last_name,
            break_reasons=e.break_reasons, break_score=e.break_score, has_me=e.has_me,
            people=sorted(({"id": int(k), "name": names.get(int(k), "?"), "count": v} for k, v in e.people.items()),
                          key=lambda x: -x["count"]),
            photos=[dict(id=p.id, name=p.name, faces=p.face_count,
                         thumb_url=storage.image_url(p.thumb_key) if p.thumb_key else None)
                    for p in sorted(photos[e.id], key=lambda p: order_key(p.name))],
        ) for e in events],
    )


# --- Reference sets: places and occasions that pin prints to a period -------------------------------------------

REF_KINDS = ("home", "family", "school", "event", "trip", "other")


class RefIn(BaseModel):
    kind: str | None = None
    label: str | None = Field(None, min_length=1, max_length=120)
    start: date | None = None
    end: date | None = None
    notes: str | None = None


class ExampleIn(BaseModel):
    status: str = Field(pattern="^(proposed|confirmed|rejected)$")


def _album_of(path_lower: str) -> str:
    return path_lower.rsplit("/", 1)[1]


def ref_json(ref: AlbumRef, examples: list) -> dict:
    return dict(
        id=ref.id, kind=ref.kind, label=ref.label, notes=ref.notes,
        start=ref.start.isoformat() if ref.start else None, end=ref.end.isoformat() if ref.end else None,
        examples=[dict(photo_id=p.id, name=p.name, album=_album_of(p.parent_path_lower), status=e.status,
                       source=e.source, thumb_url=storage.image_url(p.thumb_key) if p.thumb_key else None)
                  for e, p in sorted(examples, key=lambda ep: ({"confirmed": 0, "proposed": 1}.get(ep[0].status, 2),
                                                                ep[1].parent_path_lower, order_key(ep[1].name)))],
    )


@router.get("/refs")
def refs(session: Session = Depends(db)) -> list[dict]:
    examples = defaultdict(list)
    for e, p in session.execute(select(AlbumRefExample, Photo).join(Photo, Photo.id == AlbumRefExample.photo_id)):
        examples[e.ref_id].append((e, p))
    return [ref_json(r, examples[r.id])
            for r in session.scalars(select(AlbumRef).order_by(AlbumRef.sort, AlbumRef.id))]


@router.post("/refs")
def create_ref(body: RefIn, session: Session = Depends(db)) -> dict:
    if not body.label or body.kind not in REF_KINDS:
        raise HTTPException(422, f"Give a label and a kind ({', '.join(REF_KINDS)})")
    ref = AlbumRef(kind=body.kind, label=body.label.strip(), start=body.start, end=body.end, notes=body.notes,
                   sort=(session.scalar(select(func.max(AlbumRef.sort))) or 0) + 1)
    session.add(ref)
    try:
        session.commit()
    except IntegrityError:
        raise HTTPException(409, f"There is already a reference called {body.label!r}") from None
    return ref_json(ref, [])


@router.patch("/refs/{ref_id}")
def edit_ref(ref_id: int, body: RefIn, session: Session = Depends(db)) -> dict:
    ref = session.get(AlbumRef, ref_id) or _missing("reference")
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "kind" and v not in REF_KINDS:
            raise HTTPException(422, f"kind must be one of {', '.join(REF_KINDS)}")
        setattr(ref, k, v.strip() if k == "label" and v else v)
    try:
        session.commit()
    except IntegrityError:
        raise HTTPException(409, "There is already a reference with that label") from None
    return dict(ok=True)


@router.delete("/refs/{ref_id}", status_code=204)
def delete_ref(ref_id: int, session: Session = Depends(db)) -> None:
    session.delete(session.get(AlbumRef, ref_id) or _missing("reference"))
    session.commit()


@router.put("/refs/{ref_id}/examples/{photo_id}")
def set_example(ref_id: int, photo_id: int, body: ExampleIn, session: Session = Depends(db)) -> dict:
    """Confirm, reject or add a print as an example of a reference (adding one makes it yours, not a proposal)."""
    session.get(AlbumRef, ref_id) or _missing("reference")
    photo = session.get(Photo, photo_id)
    if photo is None or not photo.album_scan:
        _missing("album print")
    session.execute(insert(AlbumRefExample).values(ref_id=ref_id, photo_id=photo_id, status=body.status, source="user")
                    .on_conflict_do_update(index_elements=["ref_id", "photo_id"], set_=dict(status=body.status)))
    session.commit()
    return dict(ok=True)


@router.delete("/refs/{ref_id}/examples/{photo_id}", status_code=204)
def remove_example(ref_id: int, photo_id: int, session: Session = Depends(db)) -> None:
    session.execute(delete(AlbumRefExample).where(AlbumRefExample.ref_id == ref_id,
                                                  AlbumRefExample.photo_id == photo_id))
    session.commit()


def _missing(what: str):
    raise HTTPException(404, f"No such {what}")


# --- Face groups: name childhood faces a group at a time ----------------------------------------------------------

GROUP_SAMPLE = 16


def _page_label(album: str, name: str) -> str:
    page = page_of(name)
    return f"{album} p.{page}" if page is not None else f"{album} {name}"


@router.get("/face-groups/{cid}/faces")
def face_group_faces(cid: int, session: Session = Depends(db)) -> list[dict]:
    """Every face in a group, best first, so you can take out the wrong ones before naming a big group."""
    rows = session.execute(
        select(AlbumFace, Photo.name, Photo.parent_path_lower).join(Photo, Photo.id == AlbumFace.photo_id)
        .where(AlbumFace.cluster_id == cid, AlbumFace.person_id.is_(None), ~AlbumFace.ignored)
        .order_by(AlbumFace.quality.desc())
    ).all()
    return [dict(id=f.id, photo_id=f.photo_id, crop_url=storage.image_url(f.crop_key) if f.crop_key else None,
                 where=_page_label(_album_of(p), nm)) for f, nm, p in rows]


@router.get("/face-groups")
def face_groups(offset: int = 0, limit: int = Query(20, le=100), session: Session = Depends(db)) -> dict:
    """Unnamed groups, biggest first: sample faces, where in the albums they appear, and the closest named person."""
    sizes = session.execute(
        select(AlbumFace.cluster_id, func.count()).where(AlbumFace.cluster_id.is_not(None), AlbumFace.person_id.is_(None),
                                                         ~AlbumFace.ignored)
        .group_by(AlbumFace.cluster_id).order_by(func.count().desc(), AlbumFace.cluster_id)
    ).all()
    page = sizes[offset:offset + limit]
    names = dict(session.execute(select(Person.id, Person.name)).all())
    groups = []
    for cid, n in page:
        rows = session.execute(
            select(AlbumFace, Photo.name, Photo.parent_path_lower).join(Photo, Photo.id == AlbumFace.photo_id)
            .where(AlbumFace.cluster_id == cid, AlbumFace.person_id.is_(None), ~AlbumFace.ignored)
        ).all()
        rows.sort(key=lambda r: -r[0].quality)
        spots = sorted({(_album_of(p), order_key(nm)) for _, nm, p in rows})
        votes = Counter(f.match_person_id for f, _, _ in rows if f.match_person_id and (f.match_score or 0) >= 0.45)
        guess, guess_n = votes.most_common(1)[0] if votes else (None, 0)
        groups.append(dict(
            id=cid, size=n, guess_id=guess, guess_name=names.get(guess), guess_count=guess_n,
            first=_page_label(spots[0][0], spots[0][1][2]), last=_page_label(spots[-1][0], spots[-1][1][2]),
            albums=sorted({a for a, _ in spots}),
            faces=[dict(id=f.id, photo_id=f.photo_id, crop_url=storage.image_url(f.crop_key) if f.crop_key else None,
                        where=_page_label(_album_of(p), nm)) for f, nm, p in rows[:GROUP_SAMPLE]],
        ))
    named = session.execute(
        select(AlbumFace.person_id, func.count()).where(AlbumFace.person_id.is_not(None)).group_by(AlbumFace.person_id)
    ).all()
    return dict(total=len(sizes), groups=groups,
                named=sorted(({"id": pid, "name": names.get(pid, "?"), "count": c} for pid, c in named),
                             key=lambda x: -x["count"]),
                people=sorted(({"id": i, "name": nm} for i, nm in names.items()), key=lambda x: x["name"]))


class GroupAssignIn(BaseModel):
    person_id: int | None = None
    name: str | None = None
    exclude_face_ids: list[int] = []


@router.post("/face-groups/{cid}/assign")
def assign_group(cid: int, body: GroupAssignIn, session: Session = Depends(db)) -> dict:
    """Name every face in the group (except the ones you took out). A new name adds a person."""
    if body.person_id is None:
        name = (body.name or "").strip()
        if not name:
            raise HTTPException(422, "Choose a person or type a name")
        person = session.scalar(select(Person).where(func.lower(Person.name) == name.lower()))
        if person is None:
            person = Person(name=name)
            session.add(person)
            session.flush()
        pid = person.id
    else:
        pid = (session.get(Person, body.person_id) or _missing("person")).id
    n = session.execute(update(AlbumFace).where(AlbumFace.cluster_id == cid, AlbumFace.person_id.is_(None),
                                                AlbumFace.id.not_in(body.exclude_face_ids or [-1]))
                        .values(person_id=pid, cluster_id=None)).rowcount
    session.execute(update(AlbumFace).where(AlbumFace.id.in_(body.exclude_face_ids or [-1])).values(cluster_id=None))
    session.commit()
    rematch(session)
    return dict(named=n, person_id=pid)


class GroupIgnoreIn(BaseModel):
    exclude_face_ids: list[int] = []


@router.post("/face-groups/{cid}/ignore")
def ignore_group(cid: int, body: GroupIgnoreIn, session: Session = Depends(db)) -> dict:
    n = session.execute(update(AlbumFace).where(AlbumFace.cluster_id == cid, AlbumFace.person_id.is_(None),
                                                AlbumFace.id.not_in(body.exclude_face_ids or [-1]))
                        .values(ignored=True, cluster_id=None)).rowcount
    session.execute(update(AlbumFace).where(AlbumFace.id.in_(body.exclude_face_ids or [-1])).values(cluster_id=None))
    session.commit()
    return dict(ignored=n)


@router.post("/face-groups/regroup")
def regroup(session: Session = Depends(db)) -> dict:
    """Match every album face again (using the faces you just named) and regroup what's still unnamed."""
    stats = rematch(session)
    stats.update(group_faces(session))
    return dict(stats)
