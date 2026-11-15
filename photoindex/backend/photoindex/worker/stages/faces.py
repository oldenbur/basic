"""Find faces in highlights: detect and embed them from the 2048px display copy, store a 160px crop of each."""

import io
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

import numpy as np
from PIL import Image
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from photoindex import display, storage
from photoindex.faces import engine as face_engine
from photoindex.faces.cluster import quality
from photoindex.faces.people import refresh
from photoindex.models import Face, Person, Photo
from photoindex.sources import PhotoSource
from photoindex.worker.stages import claim, reset_stale

log = logging.getLogger(__name__)
BATCH = 40
MIN_FACE_PX = 40  # smaller faces (background crowds) are too blurry to recognise reliably
MIN_SCORE = 0.6
CROP_PX = 160
# Highlights only, for now: the originals you copied to a highlights folder, and highlights with no original.
SCOPE = ("in_processing_set AND NOT ignored "
         "AND (has_highlight OR (is_highlight_copy AND original_id IS NULL AND link_method = 'none'))")


def _crop(img: Image.Image, box: tuple[float, float, float, float]) -> bytes:
    """A square crop around the face with some margin, for the People pages."""
    x, y, w, h = box
    side = max(w, h) * 1.5
    cx, cy = x + w / 2, y + h / 2
    left, top = max(0, cx - side / 2), max(0, cy - side / 2)
    region = img.crop((int(left), int(top), int(min(img.width, left + side)), int(min(img.height, top + side))))
    region.thumbnail((CROP_PX, CROP_PX))
    buf = io.BytesIO()
    region.save(buf, "JPEG", quality=85)
    return buf.getvalue()


class _Old(NamedTuple):
    id: int
    x: float
    y: float
    w: float
    h: float
    person_id: int | None
    assigned_by: str | None
    ignored: bool
    rejected_person_ids: list[int] | None


def _iou(a, b) -> float:
    ix = max(0.0, min(a.x + a.w, b.x + b.w) - max(a.x, b.x))
    iy = max(0.0, min(a.y + a.h, b.y + b.h) - max(a.y, b.y))
    inter = ix * iy
    return inter / (a.w * a.h + b.w * b.h - inter) if inter else 0.0


def _carry_over(session: Session, old: list[_Old], new: list[Face], covers: dict[int, int]) -> None:
    """Detecting again (e.g. after turning a photo upright) keeps what you said about each face: a new face that
    sits where an old one was inherits its name, rejections and ignore flag, and stays a person's cover."""
    for o in old:
        if o.person_id is None and not o.ignored and not o.rejected_person_ids:
            continue
        best = max(new, key=lambda n: _iou(o, n), default=None)
        if best is None or _iou(o, best) < 0.4:
            continue
        best.person_id, best.assigned_by, best.ignored = o.person_id, o.assigned_by, o.ignored
        best.rejected_person_ids = list(o.rejected_person_ids or [])
        if o.id in covers:
            session.execute(update(Person).where(Person.id == covers[o.id]).values(cover_face_id=best.id))


def run(session: Session, source: PhotoSource, workers: int) -> Counter:
    stats: Counter = Counter()
    reset_stale(session, "face_status")
    storage.ensure_bucket()
    eng = None

    def load(item: tuple[int, str | None, str | None]) -> tuple[int, Image.Image | None, str | None]:
        pid, key, fallback = item
        err = "faces: no image"
        for k in filter(None, (key, fallback)):  # the grid thumbnail if Dropbox couldn't make a large copy
            try:
                return pid, Image.open(io.BytesIO(storage.get_bytes(k))).convert("RGB"), None
            except Exception as e:  # noqa: BLE001
                err = f"faces: {e}"[:500]
        return pid, None, err

    with ThreadPoolExecutor(workers) as pool:
        while batch := claim(session, "face_status", SCOPE, BATCH):
            eng = eng or face_engine.get_engine()
            ids = [pid for pid, _ in batch]
            keys = display.render(session, source, ids)
            thumbs = dict(session.execute(select(Photo.id, Photo.thumb_key).where(Photo.id.in_(ids))).all())
            results = []
            for pid, img, err in pool.map(load, [(i, keys.get(i), thumbs.get(i)) for i in ids]):
                if img is None:
                    results.append(dict(id=pid, face_status="error", error=err))
                    continue
                faces = [f for f in eng.detect(np.asarray(img), MIN_SCORE) if min(f.box[2], f.box[3]) >= MIN_FACE_PX]
                old = [_Old(f.id, f.x, f.y, f.w, f.h, f.person_id, f.assigned_by, f.ignored, f.rejected_person_ids)
                       for f in session.scalars(select(Face).where(Face.photo_id == pid))]
                covers = dict(session.execute(select(Person.cover_face_id, Person.id).where(
                    Person.cover_face_id.in_([o.id for o in old]))).all()) if old else {}
                session.execute(delete(Face).where(Face.photo_id == pid))  # re-run: replace
                rows = [Face(
                    photo_id=pid, x=f.box[0] / img.width, y=f.box[1] / img.height, w=f.box[2] / img.width,
                    h=f.box[3] / img.height, size_px=int(min(f.box[2], f.box[3])), det_score=round(f.score, 4),
                    quality=quality(f.score, int(min(f.box[2], f.box[3])), f.sharpness, f.landmarks),
                    embedding=f.embedding.tolist(),
                ) for f in faces]
                session.add_all(rows)
                session.flush()
                _carry_over(session, old, rows, covers)
                for row, f in zip(rows, faces, strict=True):
                    row.crop_key = storage.face_key(row.id)
                    storage.put_image(row.crop_key, _crop(img, f.box))
                results.append(dict(id=pid, face_status="done", face_count=len(faces), error=None))
                stats["faces"] += len(faces)
            session.execute(update(Photo), results)
            session.commit()
            stats.update(r["face_status"] for r in results)
            log.info("faces: %d photos (%s)", len(results), dict(stats))

    if stats["done"]:
        stats.update({f"people_{k}": v for part in refresh(session).values() for k, v in part.items()})
    return stats
