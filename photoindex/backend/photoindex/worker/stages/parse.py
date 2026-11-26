"""Classify every folder (year / event / highlights / ...) and record naming-convention issues."""

from collections import Counter

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from photoindex.models import Folder
from photoindex.naming import FolderParse, classify
from photoindex.search import folder_terms


def run(session: Session, root: str, album_folders: tuple[str, ...] = ()) -> Counter:
    rows = session.execute(
        select(Folder.id, Folder.path_lower, Folder.path_display, Folder.parent_path_lower)
        .where(~Folder.deleted)
    ).all()
    # Parents before children.
    rows.sort(key=lambda r: r.path_lower.count("/"))

    parses: dict[str, tuple[int, FolderParse, int | None]] = {}  # path_lower -> (id, parse, event_folder_id)
    updates = []
    stats: Counter = Counter()
    for r in rows:
        rel = tuple(p for p in r.path_display[len(root):].split("/") if p)
        parent = parses.get(r.parent_path_lower)
        p = classify(rel, parent[1] if parent else None) if rel and (len(rel) == 1 or parent) else None
        if p is None:
            continue
        event_folder_id = r.id if p.kind == "event" else (parent[2] if parent and p.kind == "event_sub" else None)
        parses[r.path_lower] = (r.id, p, event_folder_id)
        stats[p.kind] += 1
        stats["issues"] += bool(p.issues)
        updates.append(dict(
            id=r.id, kind=p.kind, year=p.year, event_date=p.event_date, state=p.state, event_name=p.event_name,
            event_folder_id=event_folder_id, parse_ok=p.ok,
            issues=[i.as_dict() for i in p.issues] or None, suggested_name=p.suggested_name,
            search_terms=folder_terms(rel[-1], p.event_name, p.state, p.kind),
        ))

    for i in range(0, len(updates), 2000):
        session.execute(update(Folder), updates[i : i + 2000])
    # Photos directly under the root have no folder; they're outside any YYYY.album, so ignored too.
    session.execute(text("""
        UPDATE photos ph SET ignored = new.v FROM (
            SELECT p.id, (f.id IS NULL OR f.kind = 'ignored') AS v
            FROM photos p LEFT JOIN folders f ON f.id = p.folder_id AND NOT f.deleted
        ) new
        WHERE new.id = ph.id AND ph.ignored IS DISTINCT FROM new.v
    """))
    # Prints in the scanned albums: still ignored by the library, but prepared for dating (photoindex.albums).
    album_dirs = [f"{root.rstrip('/')}/{a}".lower() for a in album_folders]
    session.execute(text("""
        UPDATE photos SET album_scan = new.v FROM (
            SELECT id, (parent_path_lower = ANY(:dirs) AND NOT deleted) AS v FROM photos
        ) new
        WHERE new.id = photos.id AND photos.album_scan IS DISTINCT FROM new.v
    """), {"dirs": album_dirs})
    stats["album_scans"] = session.scalar(text("SELECT count(*) FROM photos WHERE album_scan"))
    stats["photos_ignored"] = session.scalar(text("SELECT count(*) FROM photos WHERE ignored AND NOT deleted"))
    session.commit()
    return stats
