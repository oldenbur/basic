from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from photoindex import storage
from photoindex.api.queries import COUNT_FIELDS, folder_counts, pipeline_stats
from photoindex.db import session_factory
from photoindex.models import Folder, Photo
from photoindex.sources import get_source
from photoindex.worker.stages.link import _update_processing_set

app = FastAPI(title="PhotoIndex")


def db() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


def folder_json(f: Folder, counts: dict) -> dict:
    return dict(
        id=f.id, name=f.name, path=f.path_display, kind=f.kind, year=f.year,
        event_date=f.event_date.isoformat() if f.event_date else None, state=f.state, event_name=f.event_name,
        parse_ok=f.parse_ok, issues=f.issues or [], suggested_name=f.suggested_name, in_scope=f.in_scope,
        counts=counts.get(f.id, dict.fromkeys(COUNT_FIELDS, 0)),
    )


def photo_json(p: Photo, original: Photo | None = None) -> dict:
    # A highlight copy isn't processed itself; show its original's date and thumbnail instead.
    src = original if original is not None and p.thumb_key is None else p
    return dict(
        id=p.id, name=p.name, path=p.path_display, folder_id=p.folder_id,
        taken_at=src.taken_at.isoformat() if src.taken_at else None, lat=src.lat, lon=src.lon,
        camera=" ".join(x for x in (src.camera_make, src.camera_model) if x) or None,
        width=src.width, height=src.height, is_highlight_copy=p.is_highlight_copy, original_id=p.original_id,
        link_method=p.link_method, has_highlight=p.has_highlight, in_processing_set=p.in_processing_set,
        burst_group_id=p.burst_group_id, date_mismatch_days=p.date_mismatch_days,
        meta_status=p.meta_status, thumb_status=p.thumb_status, error=p.error,
        thumb_url=storage.image_url(src.thumb_key) if src.thumb_key else None,
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/stats")
def stats(session: Session = Depends(db)) -> dict:
    return pipeline_stats(session)


@app.get("/api/tree")
def tree(session: Session = Depends(db)) -> list[dict]:
    """Top-level folders: years plus any events sitting directly under the root."""
    counts = folder_counts(session)
    roots = session.scalars(
        select(Folder).where(~Folder.deleted, Folder.parent_id.is_(None)).order_by(Folder.name)
    ).all()
    return [folder_json(f, counts) for f in roots]


@app.get("/api/folders/{folder_id}")
def folder(folder_id: int, session: Session = Depends(db)) -> dict:
    f = session.get(Folder, folder_id)
    if f is None or f.deleted:
        raise HTTPException(404)
    counts = folder_counts(session)
    children = session.scalars(
        select(Folder).where(~Folder.deleted, Folder.parent_id == folder_id).order_by(Folder.name)
    ).all()
    crumbs, cur = [], f
    while cur is not None:
        crumbs.append(dict(id=cur.id, name=cur.name))
        cur = session.get(Folder, cur.parent_id) if cur.parent_id else None
    return dict(folder=folder_json(f, counts), children=[folder_json(c, counts) for c in children],
                breadcrumbs=crumbs[::-1])


@app.get("/api/folders/{folder_id}/photos")
def folder_photos(
    folder_id: int,
    processing_only: bool = False,
    offset: int = 0,
    limit: int = Query(200, le=1000),
    session: Session = Depends(db),
) -> dict:
    orig = aliased(Photo)
    q = (select(Photo, orig).outerjoin(orig, orig.id == Photo.original_id)
         .where(~Photo.deleted, Photo.folder_id == folder_id))
    if processing_only:
        q = q.where(Photo.in_processing_set | orig.in_processing_set)
    taken = func.coalesce(Photo.taken_at, orig.taken_at)
    rows = session.execute(q.order_by(taken.asc().nulls_last(), Photo.name).offset(offset).limit(limit + 1)).all()
    return dict(photos=[photo_json(p, o) for p, o in rows[:limit]], has_more=len(rows) > limit)


@app.get("/api/issues")
def issues(severity: str | None = None, session: Session = Depends(db)) -> list[dict]:
    counts = folder_counts(session)
    rows = session.scalars(
        select(Folder).where(~Folder.deleted, Folder.issues.is_not(None)).order_by(Folder.path_lower)
    ).all()
    out = [folder_json(f, counts) for f in rows]
    if severity:
        out = [f for f in out if any(i["severity"] == severity for i in f["issues"])]
    return out


@app.get("/api/photos/{photo_id}")
def photo(photo_id: int, session: Session = Depends(db)) -> dict:
    p = session.get(Photo, photo_id)
    if p is None:
        raise HTTPException(404)
    out = photo_json(p)
    out["copies"] = [photo_json(c) for c in session.scalars(select(Photo).where(Photo.original_id == p.id))]
    return out


@app.get("/api/photos/{photo_id}/original")
def original(photo_id: int, session: Session = Depends(db)) -> RedirectResponse:
    p = session.get(Photo, photo_id)
    if p is None:
        raise HTTPException(404)
    return RedirectResponse(get_source().temporary_link(p.path_lower))


class ScopeIn(BaseModel):
    in_scope: bool


@app.put("/api/folders/{folder_id}/scope")
def set_scope(folder_id: int, body: ScopeIn, session: Session = Depends(db)) -> dict:
    """Add/remove a folder (and everything below it) to the processing set."""
    f = session.get(Folder, folder_id)
    if f is None:
        raise HTTPException(404)
    f.in_scope = body.in_scope
    session.flush()
    _update_processing_set(session)
    session.commit()
    return folder_json(f, folder_counts(session))
