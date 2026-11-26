"""The scanned print albums: events, reference sets (places and occasions) and naming childhood faces."""

from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Integer, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.albums import dating
from photoindex.albums.faces import rematch
from photoindex.albums.names import order_key, page_of
from photoindex.albums.refs import group_faces
from photoindex.config import get_settings
from photoindex.db import session_factory
from photoindex.models import (AlbumDateAnswer, AlbumDateRun, AlbumEvent, AlbumEventOverride, AlbumFace, AlbumGroup,
                               AlbumPlacement, AlbumPrintDate, AlbumPrintMove, AlbumRef,
                               AlbumRefExample, Person, Photo)

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


# --- Dating -----------------------------------------------------------------------------------------------------

PILOT_MAX_USD = 2.0  # the pilot was approved at about $1


def _run_json(r: AlbumDateRun) -> dict:
    return dict(id=r.id, kind=r.kind, model=r.model, status=r.status, requests=r.requests, succeeded=r.succeeded,
                errored=r.errored, est_cost_usd=r.est_cost_usd, cost_usd=r.cost_usd,
                created_at=r.created_at.isoformat() if r.created_at else None)


@router.get("/dating")
def dating_status(session: Session = Depends(db)) -> dict:
    runs = session.scalars(select(AlbumDateRun).order_by(AlbumDateRun.id.desc())).all()
    dated = session.scalar(select(func.count(func.distinct(AlbumPrintDate.photo_id))))
    prints = session.scalar(select(func.count()).select_from(Photo).where(Photo.album_scan, ~Photo.deleted))
    return dict(runs=[_run_json(r) for r in runs], dated=dated, prints=prints,
                has_key=bool(get_settings().anthropic_api_key), pilot_max_usd=PILOT_MAX_USD)


@router.get("/dating/estimate")
def dating_estimate(kind: str = Query("pilot", pattern="^(pilot|rest)$"), session: Session = Depends(db)) -> dict:
    events = dating.pilot_events(session) if kind == "pilot" else dating.undated_events(session)
    if not events:
        return dict(events=0, prints=0, low=0, high=0)
    return dating.plan(session, events)[1]


class PilotIn(BaseModel):
    max_usd: float = Field(PILOT_MAX_USD, gt=0, le=PILOT_MAX_USD)


@router.post("/dating/pilot")
def start_dating_pilot(body: PilotIn, session: Session = Depends(db)) -> dict:
    if session.scalar(select(func.count()).select_from(AlbumDateRun).where(AlbumDateRun.kind == "pilot",
                                                                          AlbumDateRun.status != "failed")):
        raise HTTPException(409, "The pilot has already been sent")
    try:
        run = dating.submit(session, "pilot", dating.pilot_events(session), body.max_usd)
    except (dating.SpendLimit, ValueError) as e:
        raise HTTPException(409, str(e)) from None
    return _run_json(run)


FULL_MAX_USD = 12.0  # approved after the pilot: about $7 expected


class FullIn(BaseModel):
    max_usd: float = Field(FULL_MAX_USD, gt=0, le=FULL_MAX_USD)


@router.post("/dating/full")
def start_dating_full(body: FullIn, session: Session = Depends(db)) -> list[dict]:
    """Date every event not answered yet, in several batches."""
    try:
        runs = dating.submit_rest(session, body.max_usd)
    except (dating.SpendLimit, ValueError) as e:
        raise HTTPException(409, str(e)) from None
    return [_run_json(r) for r in runs]


@router.post("/dating/poll")
def poll_dating(session: Session = Depends(db)) -> dict:
    return dict(dating.poll(session))


@router.get("/dating/results")
def dating_results(session: Session = Depends(db)) -> list[dict]:
    """The latest answer for each event sent, in album order, with every print's estimate."""
    answers = session.scalars(select(AlbumDateAnswer).where(AlbumDateAnswer.status != "queued")
                              .order_by(AlbumDateAnswer.id.desc())).all()
    seen, latest = set(), []
    for a in answers:
        key = tuple(a.photo_ids)
        if key not in seen:
            seen.add(key)
            latest.append(a)
    ids = [pid for a in latest for pid in a.photo_ids]
    photos = {p.id: p for p in session.scalars(select(Photo).where(Photo.id.in_(ids)))}
    dates = {d.photo_id: d for d in session.scalars(
        select(AlbumPrintDate).where(AlbumPrintDate.answer_id.in_([a.id for a in latest])))}
    month = lambda d: d.strftime("%Y-%m") if d else None  # noqa: E731
    out = []
    for a in sorted(latest, key=lambda a: (a.album, a.event_seq)):
        ev = (a.result or {}).get("event", {})
        out.append(dict(
            id=a.id, album=a.album, seq=a.event_seq, status=a.status, error=a.error, cost_usd=a.cost_usd,
            summary=ev.get("summary"), best=ev.get("best"), earliest=ev.get("earliest"), latest=ev.get("latest"),
            confidence=ev.get("confidence"), clues=ev.get("clues"),
            prints=[dict(
                photo_id=pid, name=photos[pid].name if pid in photos else "?",
                thumb_url=storage.image_url(photos[pid].thumb_key) if pid in photos and photos[pid].thumb_key else None,
                **({} if (d := dates.get(pid)) is None else dict(
                    best=month(d.best), earliest=month(d.earliest), latest=month(d.latest), confidence=d.confidence,
                    reference=d.ref_label, ages=d.ages or [], different_occasion=d.different_occasion,
                    caption=d.caption)),
            ) for pid in a.photo_ids],
        ))
    return out


# --- Placement --------------------------------------------------------------------------------------------------


@router.post("/placements/run")
def run_placement(session: Session = Depends(db)) -> dict:
    from photoindex.albums import placement

    return dict(placement.run(session, get_settings().album_me))


def _placement_events(session: Session) -> tuple[list[dict], list[dict]]:
    """(per-year counts, every event in album order with its prints, decision and neighbours)."""
    from photoindex.albums.placement import ME_FROM, grouping

    g = grouping(session)
    pls = {p.photo_id: p for p in session.scalars(select(AlbumPlacement))}
    photos = {p.id: p for p in session.scalars(select(Photo).where(Photo.id.in_(list(pls))))}
    overrides = {o.key: o for o in session.scalars(select(AlbumEventOverride))}
    groups = {f"g{x.id}": x for x in session.scalars(select(AlbumGroup))}
    by_year: dict[int, Counter] = defaultdict(Counter)
    events = []
    for album in sorted(g.albums):
        keys = g.albums[album]
        for i, k in enumerate(keys):
            prints = [pls[pid] for pid in g.members[k] if pid in pls]
            if not prints:
                continue
            for pl in prints:
                by_year[pl.month.year][pl.status] += 1
            months = Counter(pl.month for pl in prints)
            st = {pl.status for pl in prints}
            o = overrides.get(k)
            if k[0] == "a":
                a = g.answers[int(k[1:])]
                label, summary = f"{album} #{a.event_seq}", (a.result or {}).get("event", {}).get("summary")
            else:
                label, summary = f"{album}, your group {k[1:]}", groups[k].summary
            events.append(dict(
                key=k, album=album, label=label, summary=summary, has_me=prints[0].has_me,
                month=months.most_common(1)[0][0].strftime("%Y-%m"),
                first=min(months).strftime("%Y-%m"), last=max(months).strftime("%Y-%m"),
                your_month=o.month.strftime("%Y-%m") if o and o.month else None,
                decision=o.status if o and o.status else ("undecided" if "review" in st else None),
                waits=any(pl.month.year >= ME_FROM for pl in prints) and not prints[0].has_me,
                prev=keys[i - 1] if i > 0 else None, next=keys[i + 1] if i + 1 < len(keys) else None,
                prints=[dict(photo_id=pl.photo_id, name=photos[pl.photo_id].name, month=pl.month.strftime("%Y-%m"),
                             status=pl.status, source=pl.source,
                             thumb_url=storage.image_url(photos[pl.photo_id].thumb_key)
                             if photos[pl.photo_id].thumb_key else None) for pl in prints],
            ))
    years = [dict(year=y, **c) for y, c in sorted(by_year.items())]
    return years, events


@router.get("/placements")
def placements(view: str = Query("review", pattern="^(review|all)$"), year: int | None = None,
               session: Session = Depends(db)) -> dict:
    """Prints per year folder, and events: those from 1995 on without you (view=review), or all of them,
    optionally for one year (any print in it)."""
    years, events = _placement_events(session)
    if view == "review":
        events = [e for e in events if e["waits"]]
    if year is not None:
        events = [e for e in events if e["first"][:4] <= str(year) <= e["last"][:4]]
    return dict(years=years, events=events)


def _rerun(session: Session) -> None:
    from photoindex.albums import placement

    placement.run(session, get_settings().album_me)


class MoveIn(BaseModel):
    photo_ids: list[int] = Field(min_length=1)
    to: str = Field(pattern=r"^(new|a\d+|g\d+)$")  # "new" makes a group of its own


@router.post("/placements/move")
def move_prints(body: MoveIn, session: Session = Depends(db)) -> dict:
    """Move prints into another event, or split them off into a new one. Kept when events or months are redone."""
    from photoindex.albums.placement import grouping

    g = grouping(session)
    where = {pid: k for k, pids in g.members.items() for pid in pids}
    if any(pid not in where for pid in body.photo_ids):
        raise HTTPException(404, "Some of those prints haven't been dated")
    albums = {g.album_of[where[pid]] for pid in body.photo_ids}
    if len(albums) > 1:
        raise HTTPException(422, "Prints from different albums can't share an event")
    album = albums.pop()
    if body.to == "new":
        first = g.answers.get(int(where[body.photo_ids[0]][1:])) if where[body.photo_ids[0]][0] == "a" else None
        grp = AlbumGroup(album=album, summary=f"Split from {album} #{first.event_seq}" if first else None)
        session.add(grp)
        session.flush()
        target = f"g{grp.id}"
    else:
        target = body.to
        if target not in g.album_of:
            raise HTTPException(404, "No such event")
        if g.album_of[target] != album:
            raise HTTPException(422, "That event is in a different album")
    for pid in body.photo_ids:
        session.execute(delete(AlbumPrintMove).where(AlbumPrintMove.photo_id == pid))
        if target != f"a{g.owner[pid]}":  # moving back where it was dated needs no record
            session.add(AlbumPrintMove(photo_id=pid, answer_id=int(target[1:]) if target[0] == "a" else None,
                                       group_id=int(target[1:]) if target[0] == "g" else None))
    session.flush()
    # groups left with no prints are dropped, with their decisions
    empty = [x.id for x in session.scalars(select(AlbumGroup)) if not session.scalar(
        select(func.count()).select_from(AlbumPrintMove).where(AlbumPrintMove.group_id == x.id))]
    if empty:
        session.execute(delete(AlbumEventOverride).where(AlbumEventOverride.key.in_([f"g{i}" for i in empty])))
        session.execute(delete(AlbumGroup).where(AlbumGroup.id.in_(empty)))
    session.commit()
    _rerun(session)
    return dict(to=target, moved=len(body.photo_ids))


class EventEditIn(BaseModel):
    status: str | None = Field(None, pattern="^(include|skip|auto)$")  # auto: back to the rule
    month: str | None = Field(None, pattern=r"^(\d{4}-(0[1-9]|1[0-2])|auto)$")


@router.put("/placements/events/{key}")
def edit_event(key: str, body: EventEditIn, session: Session = Depends(db)) -> dict:
    """Include or leave out an event, or set its month by hand. Kept when placement reruns."""
    from photoindex.albums.placement import grouping

    if key not in grouping(session).album_of:
        raise HTTPException(404, "No such event")
    o = session.get(AlbumEventOverride, key) or AlbumEventOverride(key=key)
    if body.status is not None:
        o.status = None if body.status == "auto" else body.status
    if body.month is not None:
        o.month = None if body.month == "auto" else date(int(body.month[:4]), int(body.month[5:]), 1)
    if o.status is None and o.month is None:
        if session.get(AlbumEventOverride, key):
            session.delete(o)
    else:
        session.add(o)
    session.commit()
    _rerun(session)
    return dict(key=key, status=o.status, month=o.month.strftime("%Y-%m") if o.month else None)
