"""Find faces in the album prints and match them to the people you named on the People pages.

Album faces live in their own table: childhood photos would otherwise fill the People pages and be matched to
look-alike children of the next generation. Prints scanned sideways are tried turned a quarter each way.
"""

import io
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.faces import engine as face_engine
from photoindex.faces.cluster import match, quality
from photoindex.models import AlbumFace, Face, Photo
from photoindex.sources import PhotoSource
from photoindex.worker.stages import claim, reset_stale
from photoindex.worker.stages.faces import _crop

log = logging.getLogger(__name__)
BATCH = 40
MAX_BYTES = 8 * 1024 * 1024  # whole file: the prints are 200 dpi scans of a few hundred KB
MIN_FACE_PX = 24  # in scan pixels; a face across a room in a 4x6 print is ~25-40 px at 200 dpi
MIN_SCORE = 0.6


def _detect(eng, img: Image.Image):
    """Faces in the print as scanned; if none, the best of a quarter turn either way. Returns (rotation, image,
    faces) with rotation the clockwise turn applied."""
    best = None
    for rot in (0, 90, 270):
        im = img if rot == 0 else img.rotate(-rot, expand=True)  # PIL turns counter-clockwise
        faces = [f for f in eng.detect(np.asarray(im), MIN_SCORE) if min(f.box[2], f.box[3]) >= MIN_FACE_PX]
        if faces and (best is None or sum(f.score for f in faces) > sum(f.score for f in best[2])):
            best = (rot, im, faces)
        if rot == 0 and faces:
            break
    return best or (0, img, [])


def run(session: Session, source: PhotoSource, workers: int) -> Counter:
    stats: Counter = Counter()
    reset_stale(session, "face_status")
    storage.ensure_bucket()
    eng = None

    def load(item: tuple[int, str]):
        pid, path = item
        try:
            return pid, Image.open(io.BytesIO(source.read_head(path, MAX_BYTES))).convert("RGB"), None
        except Exception as e:  # noqa: BLE001
            return pid, None, f"album faces: {e}"[:500]

    with ThreadPoolExecutor(workers) as pool:
        while batch := claim(session, "face_status", "album_scan", BATCH):
            eng = eng or face_engine.get_engine()
            results = []
            for pid, img, err in pool.map(load, batch):
                if img is None:
                    results.append(dict(id=pid, face_status="error", error=err))
                    continue
                rot, im, faces = _detect(eng, img)
                session.execute(delete(AlbumFace).where(AlbumFace.photo_id == pid))
                rows = [AlbumFace(
                    photo_id=pid, rotation=rot, x=f.box[0] / im.width, y=f.box[1] / im.height,
                    w=f.box[2] / im.width, h=f.box[3] / im.height, size_px=int(min(f.box[2], f.box[3])),
                    det_score=round(f.score, 4),
                    quality=quality(f.score, int(min(f.box[2], f.box[3])), f.sharpness, f.landmarks),
                    embedding=f.embedding.tolist(),
                ) for f in faces]
                session.add_all(rows)
                session.flush()
                for row, f in zip(rows, faces, strict=True):
                    row.crop_key = f"album_faces/160/{row.id}.jpg"
                    storage.put_image(row.crop_key, _crop(im, f.box))
                results.append(dict(id=pid, face_status="done", face_count=len(faces), width=img.width,
                                    height=img.height, error=None))
                stats["faces"] += len(faces)
                stats["turned"] += bool(faces) and rot != 0
            session.execute(update(Photo), results)
            session.commit()
            stats.update(r["face_status"] for r in results)
            log.info("album faces: %d prints (%s)", len(results), dict(stats))

    stats.update(rematch(session))
    return stats


def rematch(session: Session) -> Counter:
    """Closest named person for every album face. References: the faces you confirmed on the People pages,
    plus album faces you confirmed (so a childhood face only has to look like other childhood faces)."""
    refs = session.execute(
        select(Face.embedding, Face.person_id).where(Face.assigned_by == "user", Face.person_id.is_not(None),
                                                     ~Face.ignored)
    ).all() + session.execute(
        select(AlbumFace.embedding, AlbumFace.person_id).where(AlbumFace.person_id.is_not(None))
    ).all()
    cands = session.execute(select(AlbumFace.id, AlbumFace.embedding)).all()
    if not cands or not refs:
        return Counter()

    def stack(rows):
        return np.vstack([np.asarray(r.embedding, dtype=np.float32) for r in rows])

    ms = match(stack(cands), stack(refs), np.array([r.person_id for r in refs]))
    changes = [dict(id=c.id, match_person_id=m.person_id, match_score=round(m.score, 4)) for c, m in zip(cands, ms)]
    for i in range(0, len(changes), 2000):
        session.execute(update(AlbumFace), changes[i : i + 2000])
    session.commit()
    return Counter(matched=len(changes))
