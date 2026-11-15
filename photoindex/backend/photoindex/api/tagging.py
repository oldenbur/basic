"""AI tagging: progress and spend, the pilot comparison, the tag vocabulary, and per-photo tags and rotation."""

import hashlib
import threading
from collections import defaultdict
from collections.abc import Iterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.db import session_factory
from photoindex.models import Photo, PhotoAI, PhotoTag, Tag, TagRun
from photoindex.rotation import set_rotation
from photoindex.sources import get_source
from photoindex.tagging import batches, pricing
from photoindex.tagging.apply import refresh_terms, resolve_tag
from photoindex.tagging.vocab import CATEGORIES, normalize, tags_from
from photoindex.tagging.worker import worker

router = APIRouter(prefix="/api")
_pilot = {"starting": False, "error": None}


def db() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


# --- Progress, settings, pilot ------------------------------------------------------------------------------


@router.get("/tagging")
def tagging_status(session: Session = Depends(db)) -> dict:
    return batches.status(session) | dict(pilot_starting=_pilot["starting"], pilot_error=_pilot["error"],
                                          worker_error=worker.last_error)


class SettingsIn(BaseModel):
    daily_cap: float | None = Field(None, ge=0, le=1000)
    paused: bool | None = None


@router.put("/tagging/settings")
def tagging_settings(body: SettingsIn, session: Session = Depends(db)) -> dict:
    cfg = batches.set_config(session, **body.model_dump(exclude_none=True))
    worker.wake()
    return cfg


class PilotIn(BaseModel):
    size: int = Field(batches.PILOT_SIZE, ge=10, le=1000)


def _start_pilot(size: int) -> None:
    try:
        with session_factory()() as session:
            batches.start_pilot(session, get_source(), size)
        _pilot["error"] = None
    except Exception as e:  # noqa: BLE001  shown on the page
        _pilot["error"] = str(e)[:500]
    finally:
        _pilot["starting"] = False
        worker.wake()


@router.post("/tagging/pilot", status_code=202)
def start_pilot(body: PilotIn, session: Session = Depends(db)) -> dict:
    """Send the pilot sample to every model. Building ~300 images per model takes a little while, so it runs in
    the background; the status shows `pilot_starting` until the batches are submitted."""
    if session.scalar(select(func.count()).where(TagRun.kind == "pilot", TagRun.status != "failed")):
        raise HTTPException(409, "a pilot has already run")
    est = sum(batches.estimate(session, m, body.size) for m in pricing.MODELS)
    cfg = batches.get_config(session)
    if batches.spent_today(session) + est > cfg["daily_cap"]:
        raise HTTPException(409, f"the pilot would cost about ${est:.2f}, over today's cap of ${cfg['daily_cap']:.2f}")
    if _pilot["starting"]:
        return dict(starting=True)
    _pilot.update(starting=True, error=None)
    threading.Thread(target=_start_pilot, args=(body.size,), daemon=True).start()
    return dict(starting=True, estimate=est)


class ChooseIn(BaseModel):
    model: str


@router.post("/tagging/choose")
def choose_model(body: ChooseIn, tasks: BackgroundTasks, session: Session = Depends(db)) -> dict:
    """Use this model for every highlight: apply its pilot answers now, then let the worker tag the rest."""
    if body.model not in pricing.MODELS:
        raise HTTPException(422, "unknown model")
    applied = batches.choose(session, body.model)
    tasks.add_task(redetect_faces)  # photos its answers turned upright
    worker.wake()
    return dict(model=body.model, applied=applied)


@router.post("/tagging/poll", status_code=202)
def poll_now() -> dict:
    worker.wake()
    return dict(ok=True)


def _order(photo_id: int, ids: list[int]) -> list[int]:
    """A fixed per-photo shuffle of the models' answers, so the compare page doesn't always show them in the
    same order (you vote before seeing which model said what)."""
    return sorted(ids, key=lambda i: hashlib.md5(f"{photo_id}:{i}".encode()).hexdigest())


def answer_json(ai: PhotoAI, model: str) -> dict:
    r = ai.result or {}
    return dict(
        id=ai.id, model=model, label=pricing.MODELS[model].label if model in pricing.MODELS else model,
        status=ai.status, error=ai.error, caption=r.get("caption"), aesthetic=r.get("aesthetic"),
        rotation=r.get("rotation"), confidence=r.get("confidence"), location=r.get("location"),
        people_count=r.get("people_count"), setting=r.get("setting"),
        vehicles=r.get("vehicles") or [], tags=[f"{c}:{v}" for c, v in tags_from(r)] if r else [],
        cost_usd=ai.cost_usd, output_tokens=ai.output_tokens, best=ai.best, flags=list(ai.flags or []),
    )


@router.get("/tagging/pilot")
def pilot(session: Session = Depends(db)) -> dict:
    rows = session.execute(
        select(PhotoAI, TagRun.model, Photo).join(TagRun, TagRun.id == PhotoAI.run_id)
        .join(Photo, Photo.id == PhotoAI.photo_id).where(TagRun.kind == "pilot").order_by(PhotoAI.photo_id)
    ).all()
    by_photo: dict[int, dict] = {}
    summary: dict[str, dict] = defaultdict(lambda: dict(answers=0, done=0, best=0, flagged=0, flags=0,
                                                         cost=0.0, rotations=0, output_tokens=0))
    for ai, model, p in rows:
        item = by_photo.setdefault(p.id, dict(
            photo_id=p.id, name=p.name, thumb_url=storage.image_url(p.thumb_key) if p.thumb_key else None,
            display_url=f"/api/photos/{p.id}/display", answers={}))
        item["answers"][ai.id] = answer_json(ai, model)
        s = summary[model]
        s["answers"] += 1
        s["done"] += ai.status == "done"
        s["best"] += ai.best
        s["flagged"] += bool(ai.flags)
        s["flags"] += len(ai.flags or [])
        s["cost"] += ai.cost_usd or 0
        s["output_tokens"] += ai.output_tokens or 0
        s["rotations"] += bool((ai.result or {}).get("rotation"))
    photos = []
    for pid, item in by_photo.items():
        item["answers"] = [item["answers"][i] for i in _order(pid, list(item["answers"]))]
        item["voted"] = any(a["best"] for a in item["answers"])
        photos.append(item)
    total = session.scalar(select(func.count()).where(batches._in_scope(), ~Photo.deleted)) or 0
    models = []
    for m, s in summary.items():
        per = s["cost"] / s["done"] if s["done"] else None
        models.append(dict(model=m, label=pricing.MODELS[m].label if m in pricing.MODELS else m, **s,
                           per_photo=per, estimate_all=per * total if per is not None else None,
                           avg_output_tokens=s["output_tokens"] / s["done"] if s["done"] else None))
    order = list(pricing.MODELS)
    models.sort(key=lambda x: order.index(x["model"]) if x["model"] in order else 99)
    runs = session.scalars(select(TagRun).where(TagRun.kind == "pilot")).all()
    return dict(photos=photos, models=models, highlights=total, voted=sum(p["voted"] for p in photos),
                running=sum(r.status in ("submitted", "collecting") for r in runs), runs=len(runs))


class VoteIn(BaseModel):
    best_id: int | None = None  # the answer you think is best (None: no favourite / all equally bad)
    flags: dict[int, list[str]] = Field(default_factory=dict)  # answer id -> tags (or "caption" etc.) that are wrong


@router.post("/tagging/pilot/{photo_id}/vote")
def vote(photo_id: int, body: VoteIn, session: Session = Depends(db)) -> dict:
    answers = session.scalars(
        select(PhotoAI).join(TagRun, TagRun.id == PhotoAI.run_id)
        .where(PhotoAI.photo_id == photo_id, TagRun.kind == "pilot")
    ).all()
    if not answers:
        raise HTTPException(404)
    for a in answers:
        a.best = a.id == body.best_id
        if a.id in body.flags:
            a.flags = sorted(set(body.flags[a.id]))
    session.commit()
    return dict(ok=True)


# --- Tags -------------------------------------------------------------------------------------------------------


def _tag_counts(session: Session, ids: list[int] | None = None) -> dict[int, int]:
    q = select(PhotoTag.tag_id, func.count()).where(~PhotoTag.removed).group_by(PhotoTag.tag_id)
    if ids is not None:
        q = q.where(PhotoTag.tag_id.in_(ids))
    return dict(session.execute(q).all())


def tag_json(t: Tag, count: int) -> dict:
    return dict(id=t.id, category=t.category, value=t.value, hidden=t.hidden, count=count, key=f"{t.category}:{t.value}")


@router.get("/tags")
def list_tags(category: str | None = None, q: str = "", include_hidden: bool = True,
              session: Session = Depends(db)) -> list[dict]:
    stmt = select(Tag).where(Tag.merged_into_id.is_(None))
    if category:
        stmt = stmt.where(Tag.category == category)
    if q.strip():
        stmt = stmt.where(Tag.value.ilike(f"%{q.strip()}%"))
    if not include_hidden:
        stmt = stmt.where(~Tag.hidden)
    counts = _tag_counts(session)
    tags = [tag_json(t, counts.get(t.id, 0)) for t in session.scalars(stmt)]
    return sorted([t for t in tags if t["count"] or t["hidden"]], key=lambda t: (-t["count"], t["value"]))


def _merge(session: Session, src: Tag, dst: Tag) -> list[int]:
    """Move src's photos onto dst and send future answers for src there too. Returns photos touched."""
    photos = list(session.scalars(select(PhotoTag.photo_id).where(PhotoTag.tag_id == src.id)))
    rows = session.execute(select(PhotoTag).where(PhotoTag.tag_id == src.id)).scalars().all()
    if rows:
        session.execute(insert(PhotoTag).values([dict(photo_id=r.photo_id, tag_id=dst.id, source=r.source,
                                                      removed=r.removed) for r in rows]).on_conflict_do_nothing())
    session.execute(delete(PhotoTag).where(PhotoTag.tag_id == src.id))
    session.execute(update(Tag).where(Tag.merged_into_id == src.id).values(merged_into_id=dst.id))
    src.merged_into_id = dst.id
    return photos


class TagIn(BaseModel):
    value: str | None = None  # rename (merges if that name exists already)
    hidden: bool | None = None  # hide from filters and photo details
    merge_into_id: int | None = None


@router.patch("/tags/{tag_id}")
def edit_tag(tag_id: int, body: TagIn, session: Session = Depends(db)) -> dict:
    t = session.get(Tag, tag_id)
    if t is None:
        raise HTTPException(404)
    touched: list[int] = []
    target = t
    if body.merge_into_id is not None:
        dst = session.get(Tag, body.merge_into_id)
        if dst is None or dst.id == t.id or dst.category != t.category:
            raise HTTPException(422, "merge into another tag of the same kind")
        touched = _merge(session, t, dst)
        target = dst
    elif body.value is not None:
        new = (normalize(t.category, body.value) if t.category != "landmark" else body.value.strip()) or ""
        if not new:
            raise HTTPException(422, "empty name")
        other = session.scalars(select(Tag).where(Tag.category == t.category, func.lower(Tag.value) == new.lower(),
                                                  Tag.id != t.id)).first()
        if other is not None:
            touched = _merge(session, t, resolve_tag(session, other.category, other.value))
            target = session.get(Tag, t.merged_into_id)
        else:
            t.value = new
            touched = list(session.scalars(select(PhotoTag.photo_id).where(PhotoTag.tag_id == t.id)))
    if body.hidden is not None:
        target.hidden = body.hidden
        touched = touched or list(session.scalars(select(PhotoTag.photo_id).where(PhotoTag.tag_id == target.id)))
    session.flush()
    for p in session.scalars(select(Photo).where(Photo.id.in_(touched))) if touched else []:
        refresh_terms(session, p)
    session.commit()
    return tag_json(target, _tag_counts(session, [target.id]).get(target.id, 0))


# --- One photo --------------------------------------------------------------------------------------------------


def _canonical(session: Session, photo_id: int) -> Photo:
    """The photo that carries tags: a highlight copy's original."""
    p = session.get(Photo, photo_id)
    if p is None:
        raise HTTPException(404)
    if p.ai_id is None and p.original_id is not None:
        return session.get(Photo, p.original_id) or p
    return p


def photo_ai_json(session: Session, p: Photo) -> dict:
    rows = session.execute(
        select(Tag, PhotoTag).join(PhotoTag, PhotoTag.tag_id == Tag.id)
        .where(PhotoTag.photo_id == p.id, ~Tag.hidden).order_by(Tag.category, Tag.value)
    ).all()
    ai = session.get(PhotoAI, p.ai_id) if p.ai_id else None
    run = session.get(TagRun, ai.run_id) if ai else None
    return dict(
        photo_id=p.id, caption=p.caption, scene=p.scene, setting=p.setting, aesthetic=p.aesthetic,
        rotation=p.rotation, tag_status=p.tag_status,
        place=dict(country=p.place_country, region=p.place_region, city=p.place_city, source=p.place_source),
        place_name=((ai.result or {}).get("location") or {}).get("place_name") if ai else None,
        model=pricing.MODELS[run.model].label if run and run.model in pricing.MODELS else (run.model if run else None),
        tags=[dict(id=t.id, category=t.category, value=t.value, key=f"{t.category}:{t.value}", source=pt.source)
              for t, pt in rows if not pt.removed],
        removed=[dict(id=t.id, category=t.category, value=t.value) for t, pt in rows if pt.removed],
    )


@router.get("/photos/{photo_id}/ai")
def photo_ai(photo_id: int, session: Session = Depends(db)) -> dict:
    return photo_ai_json(session, _canonical(session, photo_id))


class TagEdit(BaseModel):
    add: list[str] = Field(default_factory=list)  # "category:value"
    remove: list[int] = Field(default_factory=list)  # tag ids


@router.patch("/photos/{photo_id}/tags")
def edit_photo_tags(photo_id: int, body: TagEdit, session: Session = Depends(db)) -> dict:
    p = _canonical(session, photo_id)
    for key in body.add:
        cat, _, value = key.partition(":")
        value = (normalize(cat, value) if cat != "landmark" else value.strip()) if cat in CATEGORIES else None
        if not value:
            raise HTTPException(422, f"bad tag {key!r}; use category:value with a category from {CATEGORIES}")
        t = resolve_tag(session, cat, value)
        session.execute(insert(PhotoTag).values(photo_id=p.id, tag_id=t.id, source="user", removed=False)
                        .on_conflict_do_update(index_elements=["photo_id", "tag_id"],
                                               set_=dict(source="user", removed=False)))
    if body.remove:
        session.execute(update(PhotoTag).where(PhotoTag.photo_id == p.id, PhotoTag.tag_id.in_(body.remove))
                        .values(source="user", removed=True))
    session.flush()
    refresh_terms(session, p)
    session.commit()
    return photo_ai_json(session, p)


class RotationIn(BaseModel):
    rotation: int = Field(ge=0, le=270)


def redetect_faces() -> None:
    """Look for faces again on photos that were just turned upright (names carry over)."""
    from photoindex.config import get_settings
    from photoindex.worker.stages import faces

    with session_factory()() as session:
        faces.run(session, get_source(), get_settings().workers)


@router.put("/photos/{photo_id}/rotation")
def rotate(photo_id: int, body: RotationIn, tasks: BackgroundTasks, session: Session = Depends(db)) -> dict:
    """Turn the photo in the app (thumbnail, slideshow copy, face boxes). Dropbox's file is left alone."""
    p = _canonical(session, photo_id)
    try:
        changed = set_rotation(session, p, body.rotation)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if changed and p.face_status == "pending":
        tasks.add_task(redetect_faces)
    return dict(photo_id=p.id, rotation=p.rotation,
                thumb_url=storage.image_url(p.thumb_key) if p.thumb_key else None)
