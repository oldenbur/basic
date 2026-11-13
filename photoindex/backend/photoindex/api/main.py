from collections.abc import Iterator
from datetime import date

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from photoindex import display, search, storage
from photoindex.api.queries import COUNT_FIELDS, folder_counts, pipeline_stats
from photoindex.db import session_factory
from photoindex.models import Folder, Photo, Theme
from photoindex.search import ThemeQuery
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
        abroad=f.kind in ("event", "event_sub") and f.state is None,
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
        display_url=f"/api/photos/{src.id}/display",
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/stats")
def stats(session: Session = Depends(db)) -> dict:
    return pipeline_stats(session)


@app.get("/api/tree")
def tree(session: Session = Depends(db)) -> list[dict]:
    """Top-level YYYY.album folders."""
    counts = folder_counts(session)
    roots = session.scalars(
        select(Folder).where(~Folder.deleted, Folder.parent_id.is_(None), Folder.kind != "ignored")
        .order_by(Folder.name)
    ).all()
    return [folder_json(f, counts) for f in roots]


@app.get("/api/folders/{folder_id}")
def folder(folder_id: int, session: Session = Depends(db)) -> dict:
    f = session.get(Folder, folder_id)
    if f is None or f.deleted:
        raise HTTPException(404)
    counts = folder_counts(session)
    children = session.scalars(
        select(Folder).where(~Folder.deleted, Folder.parent_id == folder_id, Folder.kind != "ignored")
        .order_by(Folder.name)
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
    """Folders with naming warnings, plus folders ignored for not following the scheme (severity 'ignored')."""
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


# --- Large images --------------------------------------------------------------------------------------------


@app.get("/api/photos/{photo_id}/display")
def display_image(photo_id: int, session: Session = Depends(db)) -> RedirectResponse:
    """The 2048px copy: made from Dropbox on first request, served from S3/R2 after that."""
    p = session.get(Photo, photo_id)
    if p is None or p.deleted:
        raise HTTPException(404)
    key = p.display_key or display.render(session, get_source(), [p.id]).get(p.id)
    if key is None:
        if p.thumb_key:  # Dropbox can't render it large; the grid thumbnail beats nothing
            return RedirectResponse(storage.image_url(p.thumb_key))
        raise HTTPException(404, "no image")
    return RedirectResponse(storage.image_url(key))


# --- Search --------------------------------------------------------------------------------------------------


def result_photos(session: Session, ids: list[int]) -> list[dict]:
    """photo_json for search results, in `ids` order, plus the event each photo belongs to."""
    ev = aliased(Folder)
    rows = session.execute(
        select(Photo, Folder, ev).join(Folder, Folder.id == Photo.folder_id)
        .outerjoin(ev, ev.id == Folder.event_folder_id).where(Photo.id.in_(ids))
    ).all()
    by_id = {}
    for p, f, e in rows:
        e = e or f
        by_id[p.id] = photo_json(p) | dict(
            event_name=e.event_name or e.name, event_folder_id=e.id, state=f.state,
            abroad=f.kind in ("event", "event_sub") and f.state is None,
            event_date=e.event_date.isoformat() if e.event_date else None,
        )
    return [by_id[i] for i in ids if i in by_id]


class SearchIn(BaseModel):
    query: ThemeQuery = Field(default_factory=ThemeQuery)
    sort: str = "date"
    seed: int = 0
    offset: int = 0
    limit: int = Field(200, le=1000)
    with_facets: bool = False


@app.post("/api/search")
def run_search(body: SearchIn, session: Session = Depends(db)) -> dict:
    ids = search.search_ids(session, body.query, body.sort, body.seed, body.offset, body.limit + 1)
    out = dict(photos=result_photos(session, ids[: body.limit]), has_more=len(ids) > body.limit)
    if body.offset == 0:
        out["total"] = search.count(session, body.query)
    if body.with_facets:
        out["facets"] = search.facets(session, body.query)
    return out


@app.get("/api/onthisday")
def on_this_day(month: int = Query(ge=1, le=12), day: int = Query(ge=1, le=31),
                session: Session = Depends(db)) -> list[dict]:
    try:
        today = date(date.today().year, month, day)
    except ValueError:
        raise HTTPException(422, "invalid date")
    return result_photos(session, search.on_this_day(session, today))


# --- Themes --------------------------------------------------------------------------------------------------


class ThemeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    query: ThemeQuery = Field(default_factory=ThemeQuery)
    sort: str = "event_shuffle"
    cover_photo_id: int | None = None


def theme_json(session: Session, t: Theme) -> dict:
    q = ThemeQuery.model_validate(t.query)
    cover = session.get(Photo, t.cover_photo_id) if t.cover_photo_id else None
    if cover is None:  # default cover: the theme's highest-starred photo once we have scores; the first for now
        first = search.search_ids(session, q, "date", 0, 0, 1)
        cover = session.get(Photo, first[0]) if first else None
    out = dict(
        id=t.id, name=t.name, query=q.model_dump(), sort=t.sort, cover_photo_id=t.cover_photo_id,
        cover_url=storage.image_url(cover.thumb_key) if cover is not None and cover.thumb_key else None,
        count=search.count(session, q), preparing=display.is_preparing(t.id),
    )
    ids = search.search_ids(session, q)
    out["prepared"] = session.scalar(
        select(func.count()).where(Photo.id.in_(ids), Photo.display_key.is_not(None))) if ids else 0
    return out


def _theme(session: Session, theme_id: int) -> Theme:
    t = session.get(Theme, theme_id)
    if t is None:
        raise HTTPException(404)
    return t


def _save(session: Session, t: Theme) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"a theme named '{t.name}' already exists")


@app.get("/api/themes")
def list_themes(session: Session = Depends(db)) -> list[dict]:
    return [theme_json(session, t) for t in session.scalars(select(Theme).order_by(Theme.name))]


@app.post("/api/themes", status_code=201)
def create_theme(body: ThemeIn, session: Session = Depends(db)) -> dict:
    t = Theme(name=body.name.strip(), query=body.query.model_dump(exclude_defaults=True), sort=body.sort,
              cover_photo_id=body.cover_photo_id)
    session.add(t)
    _save(session, t)
    return theme_json(session, t)


@app.get("/api/themes/{theme_id}")
def get_theme(theme_id: int, session: Session = Depends(db)) -> dict:
    return theme_json(session, _theme(session, theme_id))


@app.put("/api/themes/{theme_id}")
def update_theme(theme_id: int, body: ThemeIn, session: Session = Depends(db)) -> dict:
    t = _theme(session, theme_id)
    t.name, t.query, t.sort = body.name.strip(), body.query.model_dump(exclude_defaults=True), body.sort
    t.cover_photo_id = body.cover_photo_id
    _save(session, t)
    return theme_json(session, t)


@app.delete("/api/themes/{theme_id}", status_code=204)
def delete_theme(theme_id: int, session: Session = Depends(db)) -> None:
    session.delete(_theme(session, theme_id))
    session.commit()


@app.post("/api/themes/{theme_id}/prepare", status_code=202)
def prepare_theme(theme_id: int, tasks: BackgroundTasks, session: Session = Depends(db)) -> dict:
    """Make every large image for a theme ahead of time, so its first showing is as smooth as later ones."""
    t = _theme(session, theme_id)
    ids = search.search_ids(session, ThemeQuery.model_validate(t.query))
    tasks.add_task(display.prepare, session_factory(), get_source(), t.id, ids)
    return dict(theme_id=t.id, photos=len(ids))

