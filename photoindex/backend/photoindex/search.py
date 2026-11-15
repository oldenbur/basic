"""Search the processing set and play saved searches (themes).

A query is a `ThemeQuery`; it is stored as JSON on a theme, so new filters (people, AI tags) can be added later
with defaults and old themes keep working. Results are canonical photos: one row per distinct image (byte-identical
copies filed in two events collapse) and, by default, one shot per burst.
"""

import re
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Select, Text, and_, case, cast, exists, extract, func, literal, or_, select, true
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, aliased

from photoindex.models import Face, Folder, Person, Photo

STATE_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
    "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
    "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york", "NC": "north carolina",
    "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania",
    "RI": "rhode island", "SC": "south carolina", "SD": "south dakota", "TN": "tennessee", "TX": "texas",
    "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming", "DC": "district of columbia", "PR": "puerto rico",
}
ABROAD = "abroad"  # pseudo-state for events outside the US
SORTS = ("event_shuffle", "date", "shuffle")

# "MooseRiverBWCA" -> Moose River BWCA; "SMRLodgeSkiing" -> SMR Lodge Skiing; "Twins14mo" -> Twins 14 mo
_WORD_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


def split_words(name: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(name)]


def folder_terms(name: str, event_name: str | None, state: str | None, kind: str | None) -> str | None:
    """Space-separated search words for a folder; prefix-matched per word, so 'ski' finds 'skiing'."""
    if kind not in ("event", "event_sub"):
        return None
    words: list[str] = []
    for part in filter(None, (event_name, name if kind == "event_sub" else None)):
        words += split_words(part)
        words += [w.lower() for w in re.split(r"[\s_&.\-]+", part) if w]  # 'ABasin' -> also 'abasin'
    if state:
        words += [state.lower(), *STATE_NAMES.get(state, "").split()]
    else:
        words.append(ABROAD)
    return " ".join(dict.fromkeys(words))


class ThemeQuery(BaseModel):
    text: str = ""  # words must all match an event; "|" separates alternatives: "eldora | steamboat ski"
    year_from: int | None = None
    year_to: int | None = None
    months: list[int] = Field(default_factory=list)  # 1-12, from the photo's date
    states: list[str] = Field(default_factory=list)  # US codes, plus "abroad"
    cameras: list[str] = Field(default_factory=list)
    folder_ids: list[int] = Field(default_factory=list)  # restrict to these folders and everything below them
    has_gps: bool | None = None
    highlights_only: bool = False  # only photos you copied to a highlights folder
    collapse_bursts: bool = True
    people: list[int] = Field(default_factory=list)  # person ids
    people_all: bool = False  # True: every listed person is in the photo; False: any of them
    group: str | None = None  # "solo" (1 face), "small" (2-4), "large" (5+)


GROUP_SIZES = {"solo": (1, 1), "small": (2, 4), "large": (5, None)}


def _text_filter(text: str):
    terms = " " + func.coalesce(Folder.search_terms, "") + " "
    alternatives = []
    for alt in text.lower().split("|"):
        words = [w for w in re.split(r"[\s,]+", alt.strip()) if w]
        if not words:
            continue
        conds = []
        for w in words:
            cond = terms.like(f"% {w.replace('%', '').replace('_', '')}%")  # word prefix
            if len(w) >= 5:  # typo tolerance on longer words only; short ones would match too much
                cond = cond | (func.word_similarity(w, Folder.search_terms) >= 0.6)
            conds.append(cond)
        alternatives.append(and_(*conds))
    return or_(*alternatives) if alternatives else true()


def photo_date():
    return func.coalesce(Photo.taken_at, cast(Folder.event_date, DateTime))


def _base(q: ThemeQuery) -> Select:
    """Filtered, deduplicated photo ids with the columns ordering and facets need."""
    when = photo_date()
    conds = [Photo.in_processing_set, ~Photo.deleted, ~Photo.ignored]
    if q.text.strip():
        conds.append(_text_filter(q.text))
    if q.year_from is not None:
        conds.append(Folder.year >= q.year_from)
    if q.year_to is not None:
        conds.append(Folder.year <= q.year_to)
    if q.months:
        conds.append(extract("month", when).in_(q.months))
    if q.states:
        us = [s.upper() for s in q.states if s != ABROAD]
        state_conds = [Folder.state.in_(us)] if us else []
        if ABROAD in q.states:
            state_conds.append(Folder.kind.in_(("event", "event_sub")) & Folder.state.is_(None))
        conds.append(or_(*state_conds))
    if q.cameras:
        conds.append(Photo.camera_model.in_(q.cameras))
    if q.folder_ids:
        scope = aliased(Folder)
        conds.append(exists().where(
            scope.id.in_(q.folder_ids),
            (Photo.folder_id == scope.id) | func.starts_with(Photo.path_lower, scope.path_lower + "/"),
        ))
    if q.has_gps is not None:
        conds.append(Photo.lat.is_not(None) if q.has_gps else Photo.lat.is_(None))
    if q.highlights_only:
        conds.append(Photo.has_highlight | Photo.is_highlight_copy)
    if q.people:
        def with_person(ids):
            return exists().where(Face.photo_id == Photo.id, Face.person_id.in_(ids), ~Face.ignored)
        conds.append(and_(*[with_person([p]) for p in q.people]) if q.people_all else with_person(q.people))
    if q.group in GROUP_SIZES:
        lo, hi = GROUP_SIZES[q.group]
        conds.append(Photo.face_count >= lo)
        if hi is not None:
            conds.append(Photo.face_count <= hi)

    # One row per distinct image ('h' + hash), and per burst when collapsing. NULL || x is NULL, so coalesce
    # falls through to the next key.
    dkey = func.coalesce(literal("h") + Photo.content_hash, literal("i") + cast(Photo.id, Text))
    if q.collapse_bursts:
        dkey = func.coalesce(literal("b") + cast(Photo.burst_group_id, Text), dkey)
    return (
        select(Photo.id.label("id"), when.label("taken"),
               func.coalesce(Folder.event_folder_id, Folder.id).label("grp"), Folder.year.label("year"),
               Folder.state.label("state"), Folder.kind.label("kind"), Photo.camera_model.label("camera"))
        .join(Folder, Folder.id == Photo.folder_id)
        .where(*conds)
        .ext(distinct_on(dkey))
        .order_by(dkey, when.asc().nulls_last(), Photo.id)
    )


def _ordered(q: ThemeQuery, sort: str, seed: int) -> Select:
    d = _base(q).subquery()
    shuffle = lambda col: func.md5(cast(col, Text) + literal(f":{seed}"))  # noqa: E731  stable per seed
    order = {
        "date": (d.c.taken.asc().nulls_last(), d.c.id),
        "shuffle": (shuffle(d.c.id),),
        "event_shuffle": (shuffle(d.c.grp), d.c.taken.asc().nulls_last(), d.c.id),
    }[sort if sort in SORTS else "event_shuffle"]
    return select(d.c.id).order_by(*order)


def search_ids(session: Session, q: ThemeQuery, sort: str = "date", seed: int = 0,
               offset: int = 0, limit: int | None = None) -> list[int]:
    stmt = _ordered(q, sort, seed).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def count(session: Session, q: ThemeQuery) -> int:
    return session.scalar(select(func.count()).select_from(_base(q).subquery())) or 0


# Each facet is counted without its own filter, so picking one state still shows the others to add.
_FACET_FILTERS = {"year": ("year_from", "year_to"), "month": ("months",), "state": ("states",),
                  "camera": ("cameras",), "person": ("people", "people_all")}


def facets(session: Session, q: ThemeQuery) -> dict[str, list[dict]]:
    """Counts per year, month, state ("abroad" for events outside the US), camera and person."""
    out = {}
    for name, fields in _FACET_FILTERS.items():
        d = _base(q.model_copy(update={f: ThemeQuery.model_fields[f].get_default(call_default_factory=True)
                                       for f in fields})).subquery()
        if name == "person":
            rows = session.execute(
                select(Person.id, Person.name, func.count(func.distinct(Face.photo_id)).label("n"))
                .join(Face, Face.person_id == Person.id).join(d, d.c.id == Face.photo_id).where(~Face.ignored)
                .group_by(Person.id).order_by(func.count(func.distinct(Face.photo_id)).desc())
            ).all()
            out[name] = [{"value": pid, "label": pname, "count": n} for pid, pname, n in rows]
            continue
        col = {
            "year": d.c.year,
            "month": extract("month", d.c.taken),
            "state": case((d.c.state.is_not(None), d.c.state),
                          (d.c.kind.in_(("event", "event_sub")), literal(ABROAD)), else_=None),
            "camera": d.c.camera,
        }[name]
        rows = session.execute(
            select(col.label("value"), func.count().label("n")).where(col.is_not(None))
            .group_by(col).order_by(func.count().desc() if name in ("state", "camera") else col)
        ).all()
        out[name] = [{"value": int(v) if name == "month" else v, "count": n} for v, n in rows]
    return out


def on_this_day(session: Session, day: date, limit: int = 40) -> list[int]:
    """Highlights taken on this month/day in past years (widening to +/-3 days if there are few), newest first."""
    when = photo_date()
    for spread in (0, 3):
        doy = [date(2000, day.month, day.day).toordinal() + i for i in range(-spread, spread + 1)]
        md = [(d.month, d.day) for d in map(date.fromordinal, doy)]
        cond = or_(*[(extract("month", when) == m) & (extract("day", when) == dd) for m, dd in md])
        base = _base(ThemeQuery(highlights_only=True)).where(cond, extract("year", when) < day.year).subquery()
        ids = list(session.scalars(select(base.c.id).order_by(base.c.taken.desc()).limit(limit)))
        if len(ids) >= 6 or spread:
            return ids
    return []
