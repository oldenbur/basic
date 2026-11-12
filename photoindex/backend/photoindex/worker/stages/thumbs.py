"""Fetch Dropbox-rendered 640px thumbnails for the processing set, store them in S3/R2, compute phash."""

import io
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import imagehash
from PIL import Image
from sqlalchemy import update
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.models import Photo
from photoindex.sources import PhotoSource
from photoindex.worker.stages import claim, reset_stale

log = logging.getLogger(__name__)
BATCH = 100
CHUNK = 25  # one Dropbox get_thumbnail_batch call
THUMB_SIZE = "w640h480"


def run(session: Session, source: PhotoSource, workers: int) -> Counter:
    stats: Counter = Counter()
    reset_stale(session, "thumb_status")
    storage.ensure_bucket()

    def process(chunk: list[tuple[int, str]]) -> list[dict]:
        try:
            images = source.thumbnails([path for _, path in chunk], THUMB_SIZE)
        except Exception as e:
            return [dict(id=pid, thumb_status="error", error=f"thumbs: {e}"[:500]) for pid, _ in chunk]
        out = []
        for pid, path in chunk:
            data = images.get(path)
            if data is None:
                out.append(dict(id=pid, thumb_status="error", error="thumbs: no thumbnail (unsupported type?)"))
                continue
            key = storage.thumb_key(pid)
            storage.put_image(key, data)
            with Image.open(io.BytesIO(data)) as im:
                ph = str(imagehash.phash(im))
            out.append(dict(id=pid, thumb_status="done", thumb_key=key, phash=ph, error=None))
        return out

    with ThreadPoolExecutor(workers) as pool:
        while batch := claim(session, "thumb_status", "in_processing_set", BATCH):
            chunks = [batch[i : i + CHUNK] for i in range(0, len(batch), CHUNK)]
            results = [r for rs in pool.map(process, chunks) for r in rs]
            session.execute(update(Photo), results)
            session.commit()
            stats.update(r["thumb_status"] for r in results)
            log.info("thumbs: %d photos (%s)", len(results), dict(stats))
    return stats
