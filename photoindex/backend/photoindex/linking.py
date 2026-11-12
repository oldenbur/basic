"""Match highlight copies to their originals, and group burst shots. Pure functions, no DB."""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

# Suffixes editors and copy operations append: "IMG_1234-edited", "IMG_1234 (1)", "IMG_1234_HDR", "IMG_1234 copy"
_SUFFIX_RE = re.compile(r"(?:[ _\-]+(?:edit(?:ed)?|copy|hdr|export(?:ed)?|\d{1,2})|\s*\(\d+\))+$", re.IGNORECASE)


def normalize_stem(name: str) -> str:
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return _SUFFIX_RE.sub("", stem).lower()


@dataclass
class Candidate:
    id: int
    name: str
    year: int | None
    content_hash: str | None = None
    taken_at: datetime | None = None
    camera_model: str | None = None


@dataclass
class LinkResult:
    original_id: int | None
    method: str  # hash | stem | stem_time | ambiguous | none
    candidate_ids: tuple[int, ...] = ()  # originals that need EXIF to settle an ambiguous match


def match_highlights(highlights: list[Candidate], originals: list[Candidate]) -> dict[int, LinkResult]:
    by_hash: dict[str, list[Candidate]] = defaultdict(list)
    by_stem: dict[tuple[int | None, str], list[Candidate]] = defaultdict(list)
    for o in originals:
        if o.content_hash:
            by_hash[o.content_hash].append(o)
        by_stem[(o.year, normalize_stem(o.name))].append(o)

    out: dict[int, LinkResult] = {}
    for h in highlights:
        if h.content_hash and by_hash.get(h.content_hash):
            out[h.id] = LinkResult(by_hash[h.content_hash][0].id, "hash")
            continue
        cands = by_stem.get((h.year, normalize_stem(h.name)), [])
        if len(cands) == 1:
            out[h.id] = LinkResult(cands[0].id, "stem")
        elif not cands:
            out[h.id] = LinkResult(None, "none")
        else:
            out[h.id] = _resolve_by_time(h, cands)
    return out


def _resolve_by_time(h: Candidate, cands: list[Candidate]) -> LinkResult:
    if h.taken_at is not None:
        same = [c for c in cands if c.taken_at == h.taken_at
                and (not h.camera_model or not c.camera_model or c.camera_model == h.camera_model)]
        if len(same) == 1:
            return LinkResult(same[0].id, "stem_time")
        if not any(c.taken_at is None for c in cands):
            return LinkResult(None, "none" if not same else "ambiguous")
    # Not enough EXIF yet: ask for it on the highlight and the candidates, then retry.
    return LinkResult(None, "ambiguous", tuple(c.id for c in cands))


@dataclass
class Shot:
    id: int
    taken_at: datetime | None
    camera_model: str | None
    folder_id: int | None


def group_bursts(shots: list[Shot], gap: timedelta = timedelta(seconds=2)) -> dict[int, int]:
    """Map photo id -> burst group id (the first photo's id) for runs of >= 2 shots
    from the same camera in the same folder taken within `gap` of each other."""
    keyed: dict[tuple, list[Shot]] = defaultdict(list)
    for s in shots:
        if s.taken_at is not None:
            keyed[(s.folder_id, s.camera_model)].append(s)

    groups: dict[int, int] = {}
    for run in keyed.values():
        run.sort(key=lambda s: (s.taken_at, s.id))
        current: list[Shot] = [run[0]]
        for s in run[1:]:
            if s.taken_at - current[-1].taken_at <= gap:
                current.append(s)
            else:
                _emit(current, groups)
                current = [s]
        _emit(current, groups)
    return groups


def _emit(run: list[Shot], groups: dict[int, int]) -> None:
    if len(run) >= 2:
        for s in run:
            groups[s.id] = run[0].id
