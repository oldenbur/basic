"""Link highlight copies to their originals and compute the processing set."""

from collections import Counter

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from photoindex.linking import Candidate, match_highlights
from photoindex.models import Folder, Photo

HIGHLIGHT_KINDS = ("highlights", "highlights_sub")


def run(session: Session) -> Counter:
    session.execute(text("""
        UPDATE photos ph SET is_highlight_copy = (f.kind IN ('highlights', 'highlights_sub'))
        FROM folders f WHERE f.id = ph.folder_id
          AND ph.is_highlight_copy IS DISTINCT FROM (f.kind IN ('highlights', 'highlights_sub'))
    """))

    cols = (Photo.id, Photo.name, Folder.year, Photo.content_hash, Photo.taken_at, Photo.camera_model)
    highlights = [Candidate(*r) for r in session.execute(
        select(*cols).join(Folder, Folder.id == Photo.folder_id)
        .where(Photo.is_highlight_copy, ~Photo.deleted, ~Photo.ignored)
    ).all()]
    years = {h.year for h in highlights}
    hashes = {h.content_hash for h in highlights if h.content_hash}
    rows = session.execute(
        select(*cols, Folder.kind, Folder.issues, Photo.path_lower).join(Folder, Folder.id == Photo.folder_id)
        .where(~Photo.is_highlight_copy, ~Photo.deleted, ~Photo.ignored,
               Folder.year.in_(years) | Photo.content_hash.in_(hashes))
    ).all()
    # Prefer a proper event folder over a nested or misfiled one.
    originals = [Candidate(*r[:6], rank=(r.kind != "event", r.issues is not None, r.path_lower)) for r in rows]

    results = match_highlights(highlights, originals)
    stats = Counter(r.method for r in results.values())
    if results:
        session.execute(update(Photo), [
            dict(id=hid, original_id=r.original_id, link_method=r.method, needs_meta=r.method == "ambiguous")
            for hid, r in results.items()
        ])
    # Photos that have since become ignored drop out of linking entirely.
    session.execute(update(Photo)
                    .where(Photo.ignored, Photo.original_id.is_not(None) | Photo.link_method.is_not(None))
                    .values(original_id=None, link_method=None, needs_meta=False))
    need_exif = {cid for r in results.values() for cid in r.candidate_ids}
    if need_exif:
        session.execute(update(Photo).where(Photo.id.in_(need_exif)).values(needs_meta=True))

    session.execute(text("""
        UPDATE photos o SET has_highlight = EXISTS (
            SELECT 1 FROM photos c WHERE c.original_id = o.id AND c.is_highlight_copy AND NOT c.deleted)
        WHERE NOT o.is_highlight_copy
    """))
    _update_processing_set(session)
    session.commit()
    stats["processing_set"] = session.scalar(text("SELECT count(*) FROM photos WHERE in_processing_set"))
    return stats


def _update_processing_set(session: Session) -> None:
    session.execute(text("""
        UPDATE photos ph SET in_processing_set = new.v FROM (
            SELECT p.id, (NOT p.deleted AND NOT p.ignored AND (
                (NOT p.is_highlight_copy AND (p.has_highlight OR EXISTS (
                    SELECT 1 FROM folders s
                    WHERE s.in_scope AND NOT s.deleted AND starts_with(p.path_lower, s.path_lower || '/'))))
                -- a highlight with no findable original stands in for it
                OR (p.is_highlight_copy AND p.original_id IS NULL AND p.link_method = 'none')
            )) AS v
            FROM photos p
        ) new
        WHERE new.id = ph.id AND ph.in_processing_set IS DISTINCT FROM new.v
    """))
