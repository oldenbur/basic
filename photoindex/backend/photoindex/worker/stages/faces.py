"""Find faces in highlights: detect and embed them from the 2048px display copy, store a 160px crop of each."""

import io
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from photoindex import display, storage
from photoindex.faces import engine as face_engine
from photoindex.faces.cluster import quality
from photoindex.faces.people import refresh
from photoindex.models import Face, Photo
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
                session.execute(delete(Face).where(Face.photo_id == pid))  # re-run: replace
                rows = [Face(
                    photo_id=pid, x=f.box[0] / img.width, y=f.box[1] / img.height, w=f.box[2] / img.width,
                    h=f.box[3] / img.height, size_px=int(min(f.box[2], f.box[3])), det_score=round(f.score, 4),
                    quality=quality(f.score, int(min(f.box[2], f.box[3])), f.sharpness, f.landmarks),
                    embedding=f.embedding.tolist(),
                ) for f in faces]
                session.add_all(rows)
                session.flush()
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
