"""Settle a month for every album print from the model's estimates (step 5 of dating the albums).

The model dated each event's prints. Here:
- an event's month is the confidence-weighted median of its prints (prints flagged as a different occasion
  are left out, and keep their own date);
- a low-confidence event is pulled between its confident neighbours in album order, when that fits inside the
  model's own range for it (the albums are only roughly in order, so nothing is forced across a disagreement);
- a print that matches a dated reference (a house, trip or occasion) is kept inside that reference's dates;
- confident prints keep their own month; the rest take their event's; prints the model skipped take their event's.

Then which year folder a print belongs in: none before 1972; from 1995 on, only events you're in (the rest wait
for review).

Your edits are kept apart and applied on every run: prints moved between events or split into new ones
(album_print_moves, album_groups), and an event's decision or month (album_event_overrides). An event is keyed
"a{answer id}" (the run of prints dated together) or "g{group id}" (one you made).
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from photoindex.albums.names import order_key
from photoindex.faces.cluster import AUTO_ASSIGN
from photoindex.models import (AlbumDateAnswer, AlbumEventOverride, AlbumFace, AlbumGroup, AlbumPlacement,
                               AlbumPrintDate, AlbumPrintMove, AlbumRef, Person, Photo)

WEIGHT = {"high": 4.0, "medium": 2.0, "low": 1.0}
NEIGHBOUR_SPAN = 36  # months: confident neighbours further apart than this don't constrain what's between them
FIRST_YEAR = 1972  # older prints stay out of the year folders (for now)
ME_FROM = 1995  # from here on, only events you're in


def to_index(d: date | None) -> int | None:
    return None if d is None else d.year * 12 + d.month - 1


def to_date(i: int) -> date:
    return date(i // 12, i % 12 + 1, 1)


@dataclass
class PrintIn:
    photo_id: int
    best: int | None = None  # month index
    lo: int | None = None
    hi: int | None = None
    confidence: str | None = None
    odd: bool = False  # the model said: a different occasion from the rest of its run
    ref: tuple[int | None, int | None] | None = None  # the matched reference's dates


@dataclass
class EventIn:
    key: int | str
    prints: list[PrintIn]
    confidence: str | None = None


@dataclass
class Placed:
    month: int
    source: str  # model | event | neighbours | reference
    confidence: str
    reason: str = ""


@dataclass
class _Ev:
    month: int | None
    lo: int | None
    hi: int | None
    confidence: str
    reason: str = ""
    moved: bool = False


def _clamp(m: int, lo: int | None, hi: int | None) -> int:
    if lo is not None and m < lo:
        return lo
    if hi is not None and m > hi:
        return hi
    return m


def _wmedian(values: list[tuple[int, float]]) -> int | None:
    if not values:
        return None
    values = sorted(values)
    half, acc = sum(w for _, w in values) / 2, 0.0
    for v, w in values:
        acc += w
        if acc >= half:
            return v
    return values[-1][0]


def _own(p: PrintIn) -> int | None:
    if p.best is None:
        return None
    return _clamp(p.best, *(p.ref or (None, None)))


def place(events: list[EventIn]) -> dict[int, Placed]:
    """`events` in album order (one album at a time). Returns photo id -> placement."""
    evs: list[_Ev] = []
    for e in events:
        core = [p for p in e.prints if not p.odd and p.best is not None] or [p for p in e.prints if p.best is not None]
        month = _wmedian([(_own(p), WEIGHT.get(p.confidence or "low", 1.0)) for p in core])
        lo = _wmedian([(p.lo, 1.0) for p in core if p.lo is not None])
        hi = _wmedian([(p.hi, 1.0) for p in core if p.hi is not None])
        evs.append(_Ev(month, lo, hi, e.confidence or "low"))

    anchors = [i for i, ev in enumerate(evs) if ev.month is not None and ev.confidence in ("medium", "high")]
    for i, ev in enumerate(evs):
        if ev.confidence != "low" or ev.month is None:
            continue
        before = [a for a in anchors if a < i]
        after = [a for a in anchors if a > i]
        if not before or not after:
            continue
        p, n = evs[before[-1]].month, evs[after[0]].month
        if p > n or n - p > NEIGHBOUR_SPAN:
            continue  # neighbours out of order or far apart: they say nothing reliable about this event
        lo, hi = max(p, ev.lo if ev.lo is not None else p), min(n, ev.hi if ev.hi is not None else n)
        if lo > hi:
            continue
        new = _clamp(ev.month, lo, hi)
        if new != ev.month:
            ev.month, ev.moved = new, True
            ev.reason = f"between confident neighbours ({to_date(p):%Y-%m} and {to_date(n):%Y-%m})"

    out: dict[int, Placed] = {}
    for e, ev in zip(events, evs, strict=True):
        for p in e.prints:
            own = _own(p)
            if own is not None and (p.odd or p.confidence == "high" or ev.month is None):
                src = "reference" if own != p.best else "model"
                out[p.photo_id] = Placed(own, src, p.confidence or "low",
                                         "matches a dated reference" if src == "reference" else "")
            elif ev.month is not None:
                out[p.photo_id] = Placed(ev.month, "neighbours" if ev.moved else "event", ev.confidence,
                                         ev.reason or ("no estimate of its own" if own is None else ""))
    return out


# --- Database ----------------------------------------------------------------------------------------------------


def _me_photos(session: Session, me: str) -> set[int]:
    me_id = session.scalar(select(Person.id).where(func.lower(Person.name) == me.lower()))
    if me_id is None:
        return set()
    return set(session.scalars(select(AlbumFace.photo_id).where(
        ~AlbumFace.ignored,
        (AlbumFace.person_id == me_id) | ((AlbumFace.person_id.is_(None)) & (AlbumFace.match_person_id == me_id)
                                          & (AlbumFace.match_score >= AUTO_ASSIGN) & (AlbumFace.quality >= 0.05))))
    )


@dataclass
class Grouping:
    """Every dated print's event, after your moves, in album order."""

    members: dict[str, list[int]]  # event key -> photo ids in album order
    albums: dict[str, list[str]]  # album -> event keys in album order
    album_of: dict[str, str]
    owner: dict[int, int]  # photo id -> the answer that dated it
    answers: dict[int, AlbumDateAnswer]
    names: dict[int, str]


def grouping(session: Session) -> Grouping:
    answers = {a.id: a for a in session.scalars(select(AlbumDateAnswer).where(AlbumDateAnswer.status == "done"))}
    owner: dict[int, int] = {}
    for a in sorted(answers.values(), key=lambda x: x.id):
        for pid in a.photo_ids:
            owner[pid] = a.id  # the newest answer that covered the print
    groups = {g.id: g for g in session.scalars(select(AlbumGroup))}
    moves = {}
    for m in session.scalars(select(AlbumPrintMove)):
        if m.group_id in groups:
            moves[m.photo_id] = f"g{m.group_id}"
        elif m.answer_id in answers:
            moves[m.photo_id] = f"a{m.answer_id}"
    names = dict(session.execute(select(Photo.id, Photo.name).where(Photo.id.in_(list(owner)))).all())
    members: dict[str, list[int]] = defaultdict(list)
    for pid, aid in owner.items():
        if pid in names:
            members[moves.get(pid, f"a{aid}")].append(pid)
    album_of = {k: answers[int(k[1:])].album if k[0] == "a" else groups[int(k[1:])].album for k in members}
    albums: dict[str, list[str]] = defaultdict(list)
    for k, pids in members.items():
        pids.sort(key=lambda pid: order_key(names[pid]))
        albums[album_of[k]].append(k)
    for keys in albums.values():
        keys.sort(key=lambda k: (order_key(names[members[k][0]]), k))
    return Grouping(dict(members), dict(albums), album_of, owner, answers, names)


def _confidence(prints: list[PrintIn]) -> str:
    c = Counter(p.confidence for p in prints if p.best is not None)
    return "high" if c["high"] * 2 >= sum(c.values()) > 0 else ("medium" if c["high"] + c["medium"] else "low")


def run(session: Session, me: str) -> Counter:
    refs = {r.label: (to_index(r.start), to_index(r.end)) for r in session.scalars(select(AlbumRef))}
    latest: dict[int, AlbumPrintDate] = {}
    for d in session.scalars(select(AlbumPrintDate).order_by(AlbumPrintDate.answer_id)):
        latest[d.photo_id] = d
    g = grouping(session)
    overrides = {o.key: o for o in session.scalars(select(AlbumEventOverride))}
    me_faces = _me_photos(session, me)
    me_names = {me.lower(), me.split()[0].lower()}

    placed: dict[int, Placed] = {}
    has_me: dict[str, bool] = {}
    for keys in g.albums.values():
        evs = []
        for k in keys:
            prints = []
            for pid in g.members[k]:
                d = latest.get(pid)
                prints.append(PrintIn(pid) if d is None else PrintIn(
                    pid, to_index(d.best), to_index(d.earliest), to_index(d.latest), d.confidence,
                    d.different_occasion, refs.get(d.ref_label) if d.ref_label else None))
                seen = d is not None and any((x.get("name") or "").strip().lower() in me_names for x in d.ages or [])
                has_me[k] = has_me.get(k, False) or pid in me_faces or seen
            edited = k[0] == "g" or any(g.owner[pid] != int(k[1:]) for pid in g.members[k]) or \
                len(g.members[k]) != sum(g.owner.get(pid) == int(k[1:]) for pid in g.answers[int(k[1:])].photo_ids)
            conf = _confidence(prints) if edited else (g.answers[int(k[1:])].result or {}).get("event", {}).get("confidence")
            evs.append(EventIn(k, prints, conf))
        placed.update(place(evs))

    stats: Counter = Counter()
    rows = []
    for k, pids in g.members.items():
        o = overrides.get(k)
        for pid in pids:
            p = placed.get(pid)
            if p is None and not (o and o.month):
                stats["undated"] += 1
                continue
            month, source = (o.month, "you") if o and o.month else (to_date(p.month), p.source)
            if month.year < FIRST_YEAR:
                status, why = "older", f"before {FIRST_YEAR}"
            elif o and o.status:
                status, why = o.status, "your decision"
            elif month.year >= ME_FROM and not has_me[k]:
                status, why = "review", f"{ME_FROM} or later, and you're not recognised in this event"
            else:
                status, why = "include", ""
            reason = "your month" if source == "you" else (p.reason if p else "")
            rows.append(dict(photo_id=pid, month=month, source=source, confidence=p.confidence if p else "high",
                             status=status, reason="; ".join(x for x in (reason, why) if x) or None,
                             answer_id=g.owner[pid], event_key=k, has_me=has_me[k]))
            stats[status] += 1
    session.execute(delete(AlbumPlacement))
    for i in range(0, len(rows), 2000):
        session.execute(insert(AlbumPlacement).values(rows[i:i + 2000]))
    session.commit()
    return stats
