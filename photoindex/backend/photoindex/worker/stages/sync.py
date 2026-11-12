"""Mirror the Dropbox folder tree and image file metadata into Postgres, incrementally via a saved cursor."""

import logging
from collections import Counter
from pathlib import PurePosixPath

from sqlalchemy import case, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from photoindex.models import Folder, Photo, SyncState
from photoindex.sources import DeletedEntry, FileEntry, FolderEntry, PhotoSource, is_image

log = logging.getLogger(__name__)
CURSOR_KEY = "photos"


def _parent(path_lower: str) -> str:
    return path_lower.rsplit("/", 1)[0]


def _name(path_display: str) -> str:
    return path_display.rsplit("/", 1)[-1]


def run(session: Session, source: PhotoSource) -> Counter:
    stats: Counter = Counter()
    state = session.get(SyncState, CURSOR_KEY)
    for entries, cursor in source.list_changes(state.cursor if state else None):
        deleted = [e.path_lower for e in entries if isinstance(e, DeletedEntry)]
        # Dedupe by id (last wins): a page can contain the same item twice, e.g. moved and moved again.
        folders = list({e.id: e for e in entries
                        if isinstance(e, FolderEntry) and e.path_lower != source.root}.values())
        images = list({e.id: e for e in entries if isinstance(e, FileEntry) and is_image(e.path_lower)}.values())

        for path in deleted:
            for table in ("photos", "folders"):
                session.execute(
                    text(f"UPDATE {table} SET deleted = true "
                         f"WHERE NOT deleted AND (path_lower = :p OR starts_with(path_lower, :p || '/'))"),
                    {"p": path},
                )
        _upsert_folders(session, folders)
        _upsert_photos(session, images)
        stats.update(deleted=len(deleted), folders=len(folders), images=len(images))
        # Not indexed yet, but counted so we know how many videos / RAW files the library holds.
        stats.update("skipped" + (PurePosixPath(e.path_lower).suffix or " (none)")
                     for e in entries if isinstance(e, FileEntry) and not is_image(e.path_lower))

        state = session.merge(SyncState(key=CURSOR_KEY, cursor=cursor))
        session.commit()
        log.info("sync page: %d folders, %d images, %d deletions", len(folders), len(images), len(deleted))

    _link_parents(session)
    session.commit()
    return stats


def _upsert_folders(session: Session, folders: list[FolderEntry]) -> None:
    if not folders:
        return
    stmt = insert(Folder).values([
        dict(dropbox_id=f.id, path_lower=f.path_lower, path_display=f.path_display,
             parent_path_lower=_parent(f.path_lower), name=_name(f.path_display), deleted=False)
        for f in folders
    ])
    ex = stmt.excluded
    session.execute(stmt.on_conflict_do_update(
        index_elements=[Folder.dropbox_id],
        set_=dict(path_lower=ex.path_lower, path_display=ex.path_display,
                  parent_path_lower=ex.parent_path_lower, name=ex.name, deleted=False),
    ))


def _upsert_photos(session: Session, images: list[FileEntry]) -> None:
    for i in range(0, len(images), 1000):
        chunk = images[i : i + 1000]
        stmt = insert(Photo).values([
            dict(dropbox_id=e.id, path_lower=e.path_lower, path_display=e.path_display,
                 parent_path_lower=_parent(e.path_lower), name=_name(e.path_display), size=e.size,
                 content_hash=e.content_hash, client_modified=e.client_modified, deleted=False)
            for e in chunk
        ])
        ex = stmt.excluded
        changed = Photo.content_hash.is_distinct_from(ex.content_hash)
        session.execute(stmt.on_conflict_do_update(
            index_elements=[Photo.dropbox_id],
            set_=dict(
                path_lower=ex.path_lower, path_display=ex.path_display, parent_path_lower=ex.parent_path_lower,
                name=ex.name, size=ex.size, content_hash=ex.content_hash, client_modified=ex.client_modified,
                deleted=False,
                # A file whose bytes changed must be re-processed.
                meta_status=case((changed, "pending"), else_=Photo.meta_status),
                thumb_status=case((changed, "pending"), else_=Photo.thumb_status),
            ),
        ))


def _link_parents(session: Session) -> None:
    session.execute(text("""
        UPDATE folders f SET parent_id = p.id FROM folders p
        WHERE p.path_lower = f.parent_path_lower AND NOT p.deleted AND f.parent_id IS DISTINCT FROM p.id
    """))
    session.execute(text("""
        UPDATE photos ph SET folder_id = f.id FROM folders f
        WHERE f.path_lower = ph.parent_path_lower AND NOT f.deleted AND ph.folder_id IS DISTINCT FROM f.id
    """))
