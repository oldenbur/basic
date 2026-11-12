from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session

COUNT_FIELDS = ("photos", "processing", "thumbs", "highlights", "linked", "ignored", "issues")


def pipeline_stats(session: Session) -> dict:
    row = session.execute(text("""
        SELECT
          (SELECT count(*) FROM folders WHERE NOT deleted AND kind <> 'ignored') AS folders,
          (SELECT count(*) FROM folders WHERE NOT deleted AND kind <> 'ignored' AND issues IS NOT NULL)
            AS folders_with_issues,
          (SELECT count(*) FROM folders WHERE NOT deleted AND kind = 'ignored' AND issues IS NOT NULL)
            AS folders_ignored,
          (SELECT count(*) FROM photos WHERE NOT deleted AND ignored) AS photos_ignored,
          count(*) AS photos,
          count(*) FILTER (WHERE is_highlight_copy) AS highlight_copies,
          count(*) FILTER (WHERE is_highlight_copy AND link_method IN ('hash','stem','stem_time')) AS highlights_linked,
          count(*) FILTER (WHERE is_highlight_copy AND link_method = 'none') AS highlights_unmatched,
          count(*) FILTER (WHERE is_highlight_copy AND link_method = 'ambiguous') AS highlights_ambiguous,
          count(*) FILTER (WHERE in_processing_set) AS processing_set,
          count(*) FILTER (WHERE in_processing_set AND meta_status = 'done') AS meta_done,
          count(*) FILTER (WHERE meta_status = 'error') AS meta_errors,
          count(*) FILTER (WHERE in_processing_set AND thumb_status = 'done') AS thumbs_done,
          count(*) FILTER (WHERE thumb_status = 'error') AS thumb_errors,
          count(DISTINCT burst_group_id) AS burst_groups,
          count(*) FILTER (WHERE abs(date_mismatch_days) > 30) AS date_mismatches
        FROM photos WHERE NOT deleted AND NOT ignored
    """)).mappings().one()
    return dict(row)


def folder_counts(session: Session) -> dict[int, dict[str, int]]:
    """Per-folder counts rolled up to every ancestor (library depth is small; folders number in thousands)."""
    parents = dict(session.execute(text("SELECT id, parent_id FROM folders WHERE NOT deleted")).all())
    counts: dict[int, dict[str, int]] = defaultdict(lambda: dict.fromkeys(COUNT_FIELDS, 0))

    def add(folder_id: int | None, field: str, n: int) -> None:
        seen = set()
        while folder_id is not None and folder_id not in seen:
            seen.add(folder_id)
            counts[folder_id][field] += n
            folder_id = parents.get(folder_id)

    for r in session.execute(text("""
        SELECT folder_id, count(*) FILTER (WHERE NOT ignored) AS photos,
               count(*) FILTER (WHERE in_processing_set) AS processing,
               count(*) FILTER (WHERE in_processing_set AND thumb_status = 'done') AS thumbs,
               count(*) FILTER (WHERE is_highlight_copy) AS highlights,
               count(*) FILTER (WHERE is_highlight_copy AND original_id IS NOT NULL) AS linked,
               count(*) FILTER (WHERE ignored) AS ignored
        FROM photos WHERE NOT deleted AND folder_id IS NOT NULL GROUP BY folder_id
    """)).mappings():
        for f in ("photos", "processing", "thumbs", "highlights", "linked", "ignored"):
            add(r["folder_id"], f, r[f])
    for (fid,) in session.execute(text(
            "SELECT id FROM folders WHERE NOT deleted AND kind <> 'ignored' AND issues IS NOT NULL")):
        add(fid, "issues", 1)
    return counts
