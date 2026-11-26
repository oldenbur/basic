"""Reference sets for dating the albums: places and occasions that pin prints to a period, and childhood faces.

The starting list comes from the family timeline. Proposed example prints are guesses (from looking at the
albums) that wait for you to confirm or reject; only confirmed ones are used for dating.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from photoindex.albums.names import order_key, page_of
from photoindex.faces.cluster import cluster
from photoindex.models import AlbumFace, AlbumRef, AlbumRefExample, Photo

MIN_GROUP_QUALITY = 0.05  # backs of heads and blurred profiles don't group usefully


@dataclass
class Seed:
    kind: str
    label: str
    start: date | None = None
    end: date | None = None
    notes: str | None = None
    # (album, print names) proposed as examples, and (album, first page, last page) to pick face-free prints from.
    prints: list[tuple[str, str]] = field(default_factory=list)
    pages: tuple[str, int, int] | None = None


SEEDS = [
    Seed("home", "Galena house", date(1972, 12, 1), date(1979, 4, 30), "house with a wooden deck and railing",
         [("albums1", "scan0063.6.JPG"), ("albums1", "scan0055.1.JPG"), ("albums1", "scan0066.5.JPG")]),
    Seed("home", "Rochester house (1979-83)", date(1979, 4, 1), date(1983, 12, 31), None,
         [("albums2", "scan0012.2.JPG"), ("albums2", "scan0012.3.JPG")]),
    Seed("home", "Danbury house", date(1983, 12, 1), date(1985, 12, 31), "white colonial with black shutters",
         [("albums3", "scan0035.4.jpg"), ("albums3", "scan0035.5.jpg"), ("albums2", "scan0010.5.JPG")]),
    Seed("home", "Rochester house (1985-)", date(1985, 12, 1), None, "dark brown wood house",
         [("albums3", "scan0194.3.jpg"), ("albums3", "scan0194.4.jpg"), ("albums3", "scan0195.2.jpg"),
          ("albums3", "scan0197.3.jpg")]),
    Seed("family", "Feeley grandparents' home"),
    Seed("family", "Oldenburg grandparents' home"),
    Seed("school", "School"),
    Seed("event", "Mark & Ann's wedding", date(1972, 12, 1), date(1972, 12, 31), "winter wedding",
         [("albums1", "scan0017.1.JPG"), ("albums1", "scan0017.2.JPG")]),
    Seed("event", "Mark's MBA graduation, Notre Dame", date(1975, 6, 1), date(1975, 6, 30), None,
         pages=("albums1", 30, 30)),
    Seed("trip", "Itasca", date(1988, 7, 1), date(1988, 7, 31), "canoes", pages=("albums3", 693, 693)),
    Seed("trip", "Colorado / Grand Canyon", date(1990, 7, 1), date(1990, 7, 31), "Mesa Verde, Grand Canyon, Pikes Peak",
         pages=("albums3", 284, 305)),
    Seed("trip", "Niagara Falls", date(1991, 7, 1), date(1991, 7, 31), None, pages=("albums3", 384, 389)),
    Seed("trip", "Glacier / BC", date(1993, 7, 1), date(1993, 7, 31), "Glacier, Banff", pages=("albums3", 452, 462)),
]
PAGE_PICKS = 4  # face-free prints proposed from a page range


def seed(session: Session) -> Counter:
    """Add the starting references that don't exist yet, with their proposed examples. Never touches a reference
    or example you've already edited."""
    stats: Counter = Counter()
    have = set(session.scalars(select(AlbumRef.label)))
    prints = {(r.parent_path_lower.rsplit("/", 1)[1], r.name.lower()): r for r in session.execute(
        select(Photo.id, Photo.name, Photo.parent_path_lower, Photo.face_count).where(Photo.album_scan, ~Photo.deleted)
    )}
    for i, s in enumerate(SEEDS):
        if s.label in have:
            continue
        ref = AlbumRef(kind=s.kind, label=s.label, start=s.start, end=s.end, notes=s.notes, sort=i)
        session.add(ref)
        session.flush()
        ids = [prints[(a, n.lower())].id for a, n in s.prints if (a, n.lower()) in prints]
        if s.pages:
            album, first, last = s.pages
            pages = sorted((r for (a, _), r in prints.items() if a == album and first <= (page_of(r.name) or 0) <= last),
                           key=lambda r: order_key(r.name))
            pool = [r for r in pages if not r.face_count] or pages  # scenery first; people if that's all there is
            step = max(1, len(pool) // PAGE_PICKS)
            ids += [r.id for r in pool[::step][:PAGE_PICKS]]
        for pid in ids:
            session.execute(insert(AlbumRefExample).values(ref_id=ref.id, photo_id=pid, status="proposed",
                                                           source="claude").on_conflict_do_nothing())
        stats["refs"] += 1
        stats["proposed"] += len(ids)
    session.commit()
    return stats


def group_faces(session: Session) -> Counter:
    """Group the album faces nobody has named yet, so a childhood face can be named once for the whole group."""
    rows = session.execute(
        select(AlbumFace.id, AlbumFace.embedding).where(AlbumFace.person_id.is_(None), ~AlbumFace.ignored,
                                                        AlbumFace.quality >= MIN_GROUP_QUALITY).order_by(AlbumFace.id)
    ).all()
    session.execute(update(AlbumFace).values(cluster_id=None))
    if not rows:
        session.commit()
        return Counter()
    labels = cluster(np.vstack([np.asarray(r.embedding, dtype=np.float32) for r in rows]))
    first: dict[int, int] = {}
    changes = []
    for r, label in zip(rows, labels, strict=True):
        if label >= 0:
            changes.append(dict(id=r.id, cluster_id=first.setdefault(int(label), r.id)))
    for i in range(0, len(changes), 2000):
        session.execute(update(AlbumFace), changes[i : i + 2000])
    session.commit()
    return Counter(groups=len(first), grouped=len(changes), faces=len(rows))
