"""Split each scanned album into events: runs of consecutive prints from one roll or one occasion.

Prints are in album order (page, then position on the page). A new event starts where the prints around a gap
look different from each other (colour: film stock, season, light, fading all shift between rolls), where the
print size changes (each roll came back from the lab at one size), and, weakly, at a page turn. The same
people on both sides of a gap argue against a break.
"""

import io
import logging
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.albums.names import order_key, page_of
from photoindex.faces.cluster import AUTO_ASSIGN
from photoindex.models import AlbumEvent, AlbumFace, Person, Photo

log = logging.getLogger(__name__)
DPI = 200  # the albums were scanned at 200 dpi, so pixel size gives print size
WINDOW = 3  # prints compared on each side of a gap
THRESHOLD = 2.6
SIZE_JUMP = 1.5
PAGE_TURN = 0.3
SAME_PEOPLE = 0.7
# A roll was 12, 24 or 36 exposures, so a longer run (where faded prints all share one colour cast) is split
# again at its strongest gaps, as long as they clear this lower bar.
MAX_RUN = 24
WEAK_THRESHOLD = 1.0
# Faces this poor (backs of heads, blurred profiles, pets) match someone at random, so they don't count.
MIN_FACE_QUALITY = 0.05
# Two prints are different sizes when a side differs by more than this (inches); scan crops trim a little.
SIZE_TOL = (0.3, 0.45)


@dataclass
class Print:
    hist: np.ndarray | None  # colour histogram, sums to 1
    size: tuple[float, float] | None = None  # short, long side in inches
    page: int | None = None
    people: frozenset[int] = field(default_factory=frozenset)


@dataclass
class Break:
    at: int  # index of the first print of the new event
    score: float
    reasons: list[str]


def colour_hist(jpeg: bytes) -> np.ndarray:
    """Hue x saturation x value histogram of the print, ignoring a margin where borders and scan edges sit."""
    with Image.open(io.BytesIO(jpeg)) as im:
        a = np.asarray(im.convert("RGB").resize((128, 128)))
    a = a[6:-6, 6:-6]
    hsv = cv2.cvtColor(np.ascontiguousarray(a), cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [12, 4, 4], [0, 180, 0, 256, 0, 256]).ravel()
    return h / max(h.sum(), 1)


def _chi2(a: np.ndarray, b: np.ndarray) -> float:
    return float(0.5 * np.sum((a - b) ** 2 / (a + b + 1e-9)))


def _mean_dist(xs: list[np.ndarray], ys: list[np.ndarray] | None = None) -> float:
    if ys is None:
        pairs = [(xs[i], xs[j]) for i in range(len(xs)) for j in range(i + 1, len(xs))]
    else:
        pairs = [(x, y) for x in xs for y in ys]
    return float(np.mean([_chi2(x, y) for x, y in pairs])) if pairs else 0.0


def _size_differs(a, b) -> bool:
    return a is not None and b is not None and (abs(a[0] - b[0]) > SIZE_TOL[0] or abs(a[1] - b[1]) > SIZE_TOL[1])


def gap_scores(prints: list[Print]) -> list[Break]:
    """A score for every gap (before print 1..n-1): how much it looks like the start of a new event."""
    n = len(prints)
    contrast = np.zeros(n)
    for b in range(1, n):
        left = [p.hist for p in prints[max(0, b - WINDOW):b] if p.hist is not None]
        right = [p.hist for p in prints[b:b + WINDOW] if p.hist is not None]
        if left and right:
            # How much prints differ within a roll; a side with one print (album ends) can't say.
            spreads = [_mean_dist(side) for side in (left, right) if len(side) > 1]
            within = float(np.mean(spreads)) if spreads else 0.0
            contrast[b] = max(0.0, _mean_dist(left, right) - within)
    scale = float(np.median(contrast[1:][contrast[1:] > 0])) if (contrast[1:] > 0).any() else 1.0
    out = []
    for b in range(1, n):
        colour = contrast[b] / scale
        score, reasons = colour, ["colour"] if colour >= 2 else []
        if _size_differs(prints[b - 1].size, prints[b].size):
            score += SIZE_JUMP
            reasons.append("print size")
        pa, pb = prints[b - 1].page, prints[b].page
        if pa is not None and pb is not None:
            score += PAGE_TURN if pa != pb else -PAGE_TURN
            if pa != pb:
                reasons.append("new page")
        near_l = set().union(*(p.people for p in prints[max(0, b - 2):b]))
        near_r = set().union(*(p.people for p in prints[b:b + 2]))
        if near_l & near_r:
            score -= SAME_PEOPLE
            reasons.append("same people (against)")
        out.append(Break(b, round(score, 3), reasons))
    return out


def segment(prints: list[Print], threshold: float = THRESHOLD) -> list[Break]:
    """The gaps where new events start: strong enough, and the strongest within one print either way.
    The first event's Break is at 0 with no score."""
    gaps = gap_scores(prints)
    by_at = {g.at: g for g in gaps}
    cuts = [g for g in gaps if g.score >= threshold
            and g.score >= getattr(by_at.get(g.at - 1), "score", -1e9)
            and g.score > getattr(by_at.get(g.at + 1), "score", -1e9)]

    def split_long(start: int, end: int) -> list[Break]:
        if end - start <= MAX_RUN:
            return []
        inner = [by_at[b] for b in range(start + 3, end - 2)]  # leave at least 3 prints a side
        best = max(inner, key=lambda g: g.score, default=None)
        if best is None or best.score < min(WEAK_THRESHOLD, threshold):
            return []
        best = Break(best.at, best.score, best.reasons + ["long run"])
        return split_long(start, best.at) + [best] + split_long(best.at, end)

    bounds = [0] + [c.at for c in cuts] + [len(prints)]
    extra = [b for lo, hi in zip(bounds, bounds[1:]) for b in split_long(lo, hi)]
    return [Break(0, 0.0, [])] + sorted(cuts + extra, key=lambda g: g.at)


def run(session: Session, me: str, workers: int = 8) -> Counter:
    stats: Counter = Counter()
    me_id = session.scalar(select(Person.id).where(func.lower(Person.name) == me.lower()))
    rows = session.execute(
        select(Photo.id, Photo.name, Photo.parent_path_lower, Photo.thumb_key, Photo.width, Photo.height)
        .where(Photo.album_scan, ~Photo.deleted)
    ).all()
    people: dict[int, set[int]] = defaultdict(set)
    for pid, person, matched, score in session.execute(
        select(AlbumFace.photo_id, AlbumFace.person_id, AlbumFace.match_person_id, AlbumFace.match_score)
        .where((AlbumFace.quality >= MIN_FACE_QUALITY) | AlbumFace.person_id.is_not(None))
    ):
        who = person if person is not None else (matched if (score or 0) >= AUTO_ASSIGN else None)
        if who is not None:
            people[pid].add(who)

    def hist(key: str | None) -> np.ndarray | None:
        try:
            return colour_hist(storage.get_bytes(key)) if key else None
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(workers) as pool:
        hists = dict(zip([r.id for r in rows], pool.map(hist, [r.thumb_key for r in rows]), strict=True))
    stats["no_thumbnail"] = sum(h is None for h in hists.values())

    albums: dict[str, list] = defaultdict(list)
    for r in rows:
        albums[r.parent_path_lower.rsplit("/", 1)[1]].append(r)

    session.execute(update(Photo).where(Photo.album_scan).values(album_event_id=None))
    session.execute(delete(AlbumEvent))
    for album, items in sorted(albums.items()):
        items.sort(key=lambda r: order_key(r.name))
        prints = [Print(
            hist=hists[r.id],
            size=(min(r.width, r.height) / DPI, max(r.width, r.height) / DPI) if r.width and r.height else None,
            page=page_of(r.name), people=frozenset(people.get(r.id, ())),
        ) for r in items]
        cuts = segment(prints)
        bounds = [c.at for c in cuts] + [len(items)]
        for seq, (cut, start, end) in enumerate(zip(cuts, bounds, bounds[1:]), 1):
            members = items[start:end]
            counts = Counter(p for r in members for p in people.get(r.id, ()))
            ev = AlbumEvent(album=album, seq=seq, size=len(members), first_name=members[0].name,
                            last_name=members[-1].name, break_reasons=cut.reasons,
                            break_score=cut.score if start else None,
                            people={str(k): v for k, v in counts.items()}, has_me=me_id in counts)
            session.add(ev)
            session.flush()
            session.execute(update(Photo).where(Photo.id.in_([r.id for r in members])).values(album_event_id=ev.id))
            stats["events"] += 1
            stats["events_with_me"] += ev.has_me
        log.info("album events: %s: %d prints, %d events", album, len(items), len(cuts))
    session.commit()
    stats["prints"] = len(rows)
    return stats
