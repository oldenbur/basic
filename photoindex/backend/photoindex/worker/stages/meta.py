"""Read EXIF from the head of each file, flag date mismatches with the event folder, group bursts."""

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from photoindex.exif import parse_exif
from photoindex.linking import Shot, group_bursts
from photoindex.models import Photo
from photoindex.sources import PhotoSource
from photoindex.worker.stages import claim, reset_stale

log = logging.getLogger(__name__)
BATCH = 200


def run(session: Session, source: PhotoSource, head_bytes: int, workers: int) -> Counter:
    stats: Counter = Counter()
    reset_stale(session, "meta_status")

    def fetch(item: tuple[int, str]) -> dict:
        pid, path = item
        try:
            info = parse_exif(source.read_head(path, head_bytes))
            return dict(id=pid, meta_status="done", error=None, **vars(info))
        except Exception as e:  # one unreadable file shouldn't stop the stage
            return dict(id=pid, meta_status="error", error=f"meta: {e}"[:500])

    with ThreadPoolExecutor(workers) as pool:
        while batch := claim(session, "meta_status", "in_processing_set OR needs_meta", BATCH):
            results = list(pool.map(fetch, batch))
            session.execute(update(Photo), results)
            session.commit()
            stats.update(r["meta_status"] for r in results)
            log.info("meta: %d photos (%s)", len(results), dict(stats))

    _date_mismatch(session)
    stats["bursts"] = _bursts(session)
    session.commit()
    return stats


def _date_mismatch(session: Session) -> None:
    session.execute(text("""
        UPDATE photos ph SET date_mismatch_days = abs(ph.taken_at::date - ev.event_date)
        FROM folders f JOIN folders ev ON ev.id = f.event_folder_id
        WHERE f.id = ph.folder_id AND ph.taken_at IS NOT NULL AND ev.event_date IS NOT NULL
    """))


def _bursts(session: Session) -> int:
    shots = [Shot(*r) for r in session.execute(
        select(Photo.id, Photo.taken_at, Photo.camera_model, Photo.folder_id)
        .where(Photo.in_processing_set, Photo.taken_at.is_not(None))
    ).all()]
    groups = group_bursts(shots)
    session.execute(update(Photo).where(Photo.in_processing_set).values(burst_group_id=None))
    if groups:
        session.execute(update(Photo), [dict(id=pid, burst_group_id=g) for pid, g in groups.items()])
    return len(set(groups.values()))
