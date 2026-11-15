"""Where each photo in the processing set was taken: offline reverse geocoding of EXIF GPS, else the event folder's
US state. Photos with neither (trips abroad without GPS, unmatched highlights) get the AI's guess when tagged."""

import logging
from collections import Counter

import reverse_geocode
from sqlalchemy import select, update
from sqlalchemy.orm import Session, aliased

from photoindex.models import Folder, Photo
from photoindex.search import STATE_NAMES

log = logging.getLogger(__name__)
US = "United States"
BATCH = 5000


def state_name(code: str) -> str | None:
    name = STATE_NAMES.get(code.upper())
    return " ".join(w if w == "of" else w.capitalize() for w in name.split()) if name else None


def run(session: Session) -> Counter:
    stats: Counter = Counter()
    ev = aliased(Folder)
    # Not placed yet, or placed from the folder/AI before GPS turned up (EXIF is read after the first pass).
    has_gps = Photo.lat.is_not(None) & Photo.lon.is_not(None)
    todo = Photo.place_source.is_(None) | (has_gps & (Photo.place_source != "gps"))
    while True:
        rows = session.execute(
            select(Photo.id, Photo.lat, Photo.lon, Photo.place_source, Folder.state, ev.state)
            .outerjoin(Folder, Folder.id == Photo.folder_id).outerjoin(ev, ev.id == Folder.event_folder_id)
            .where(Photo.in_processing_set, ~Photo.deleted, ~Photo.ignored, todo,
                   has_gps | Folder.state.is_not(None) | ev.state.is_not(None))
            .order_by(Photo.id).limit(BATCH)
        ).all()
        if not rows:
            break
        gps = [r for r in rows if r.lat is not None and r.lon is not None]
        found = reverse_geocode.search([(r.lat, r.lon) for r in gps]) if gps else []
        updates = []
        for r, place in zip(gps, found, strict=True):
            updates.append(dict(id=r.id, place_country=place.get("country"), place_region=place.get("state"),
                                place_city=place.get("city"), place_source="gps"))
        for r in rows:
            if r.lat is None or r.lon is None:
                code = r[4] or r[5]
                updates.append(dict(id=r.id, place_country=US, place_region=state_name(code), place_city=None,
                                    place_source="folder"))
        session.execute(update(Photo), updates)
        session.commit()
        stats.update(u["place_source"] for u in updates)
    log.info("places: %s", dict(stats))
    return stats

