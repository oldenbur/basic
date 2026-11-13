"""2048px slideshow copies: rendered by Dropbox on first view (or ahead of time by "Prepare"), then kept in S3/R2."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.models import Photo
from photoindex.sources import PhotoSource

log = logging.getLogger(__name__)
DISPLAY_SIZE = "w2048h1536"  # Dropbox's largest rendered size
# Images per get_thumbnail_batch call. Dropbox allows 25, but at 2048px a full batch is ~10MB of base64 and
# fails with HTTP 500 often enough to matter; small batches still run in parallel.
CHUNK = 5

_preparing: set[int] = set()  # theme ids with a prepare running in this process
_lock = threading.Lock()


def source_paths(session: Session, ids: list[int]) -> dict[int, str]:
    """Where to render each photo from. A highlight copy is preferred over its original: when you re-exported
    a highlight (cropped, color-corrected), that edited version is the one you meant to show."""
    paths = dict(session.execute(select(Photo.id, Photo.path_lower).where(Photo.id.in_(ids))).all())
    for orig_id, path in session.execute(
        select(Photo.original_id, Photo.path_lower)
        .where(Photo.original_id.in_(ids), Photo.is_highlight_copy, ~Photo.deleted)
        .order_by(Photo.original_id, Photo.id)
    ):
        paths[orig_id] = path
    return paths


def render(session: Session, source: PhotoSource, ids: list[int], workers: int = 4) -> dict[int, str | None]:
    """Make display copies for `ids` that don't have one yet. Returns id -> display key (None if Dropbox can't
    render it)."""
    have = dict(session.execute(
        select(Photo.id, Photo.display_key).where(Photo.id.in_(ids), Photo.display_key.is_not(None))
    ).all())
    todo = [i for i in ids if i not in have]
    if not todo:
        return have
    paths = source_paths(session, todo)

    def fetch(chunk: list[int]) -> dict[str, bytes | None]:
        try:
            return source.thumbnails([paths[i] for i in chunk], DISPLAY_SIZE)
        except Exception:
            if len(chunk) == 1:
                log.warning("display: Dropbox couldn't render %s", paths[chunk[0]], exc_info=True)
                return {}
            # One bad file (or a flaky batch) shouldn't sink the others: retry them one at a time.
            return {k: v for i in chunk for k, v in fetch([i]).items()}

    def one_chunk(chunk: list[int]) -> dict[int, str | None]:
        images = fetch(chunk)
        out = {}
        for i in chunk:
            data = images.get(paths[i])
            if data:
                storage.put_image(storage.display_key(i), data)
            out[i] = storage.display_key(i) if data else None
        return out

    chunks = [todo[i : i + CHUNK] for i in range(0, len(todo), CHUNK)]
    with ThreadPoolExecutor(min(workers, len(chunks))) as pool:
        made = {k: v for r in pool.map(one_chunk, chunks) for k, v in r.items()}
    done = [dict(id=i, display_key=k) for i, k in made.items() if k]
    if done:
        session.execute(update(Photo), done)
        session.commit()
    return have | made


def is_preparing(theme_id: int) -> bool:
    return theme_id in _preparing


def prepare(session_factory, source: PhotoSource, theme_id: int, ids: list[int], batch: int = 200) -> None:
    """Render every missing display copy for a theme. Runs in the background; one at a time per theme."""
    with _lock:
        if theme_id in _preparing:
            return
        _preparing.add(theme_id)
    try:
        with session_factory() as session:
            for i in range(0, len(ids), batch):
                render(session, source, ids[i : i + batch])
                log.info("prepare theme %d: %d/%d", theme_id, min(i + batch, len(ids)), len(ids))
    except Exception:
        log.exception("prepare theme %d failed", theme_id)
    finally:
        _preparing.discard(theme_id)
