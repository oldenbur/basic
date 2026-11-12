"""Classify library folders and validate the naming convention.

Layout under the photo root:
    YYYY.album/                     year folder; any other top-level folder is ignored
    YYYY.album/yyMMDD.ST.event/     event in the US (yy must match YYYY)
    YYYY.album/yyMMDD.place/        event outside the US, named for the city or location
    YYYY.album/yy.highlights/       copies of the year's best photos (plain "highlights" also accepted)
Any other folder inside a year is ignored, along with everything below it. Folders inside an event or
highlights folder inherit from it.
"""

import re
from dataclasses import dataclass, field
from datetime import date

YEAR_RE = re.compile(r"^(?P<year>\d{4})\.album$")
EVENT_RE = re.compile(r"^(?P<date>\d{6})\.(?P<state>[A-Za-z]{2})\.(?P<event>\S.*)$")
ABROAD_RE = re.compile(r"^(?P<date>\d{6})\.(?P<place>\S.*)$")
HIGHLIGHTS_RE = re.compile(r"^(?:(?P<yy>\d{2})\.)?highlights?$", re.IGNORECASE)
# Dropbox sync conflicts: "name (Paul Oldenburg's conflicted copy 2026-01-30)".
CONFLICT_RE = re.compile(r"\([^()]*conflicted copy[^()]*\)\s*$", re.IGNORECASE)
# Loose shape, used only to suggest a compliant name for an ignored folder: 6- or 8-digit date, any separators.
LOOSE_RE = re.compile(r"^(?P<date>\d{8}|\d{6})[._\-\s]+(?:(?P<state>[A-Za-z]{2})[._\-\s]+)?(?P<event>\S.*)$")

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
    "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split()
)


@dataclass
class Issue:
    code: str
    severity: str  # warning | ignored
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass
class FolderParse:
    kind: str  # year | event | event_sub | highlights | highlights_sub | ignored
    year: int | None = None
    event_date: date | None = None
    state: str | None = None  # None on an event = outside the US; event_name is then the place
    event_name: str | None = None
    issues: list[Issue] = field(default_factory=list)
    suggested_name: str | None = None

    @property
    def ok(self) -> bool:
        return self.kind != "ignored"

    @property
    def abroad(self) -> bool:
        return self.kind in ("event", "event_sub") and self.state is None


def _ignored(reason: str, year: int | None = None, suggested: str | None = None) -> FolderParse:
    return FolderParse(kind="ignored", year=year, issues=[Issue("ignored", "ignored", reason)],
                       suggested_name=suggested)


def _parse_date(digits: str, year: int | None) -> date | None:
    try:
        if len(digits) == 8:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
        century = (year - year % 100) if year else 2000
        return date(century + int(digits[:2]), int(digits[2:4]), int(digits[4:]))
    except ValueError:
        return None


def _suggest(name: str, year: int | None) -> str | None:
    """A compliant spelling of a near-miss like '160101_CA_new year', if there is one."""
    m = LOOSE_RE.match(name)
    if not m or not m["state"] or m["state"].upper() not in US_STATES:
        return None
    d = _parse_date(m["date"], year)
    return f"{d:%y%m%d}.{m['state'].upper()}.{m['event'].strip()}" if d else None


def parse_event_name(name: str, year: int | None) -> FolderParse:
    """Parse a folder directly inside a year folder as an event; anything non-compliant is ignored."""
    m = EVENT_RE.match(name)
    if m:
        p = FolderParse(kind="event", year=year, state=m["state"].upper(), event_name=m["event"].strip())
        if m["state"] != m["state"].upper():
            p.issues.append(Issue("state_case", "warning", "state code should be upper case"))
            p.suggested_name = f"{m['date']}.{p.state}.{p.event_name}"
        if p.state not in US_STATES:
            p.issues.append(Issue("unknown_state", "warning", f"'{p.state}' is not a US state code"))
    elif m := ABROAD_RE.match(name):
        p = FolderParse(kind="event", year=year, event_name=m["place"].strip())
    else:
        return _ignored("doesn't match yyMMDD.ST.event or yyMMDD.place", year, _suggest(name, year))

    p.event_date = _parse_date(m["date"], year)
    if p.event_date is None:
        return _ignored(f"'{m['date']}' is not a valid yyMMDD date", year)
    if year and p.event_date.year != year:
        p.issues.append(Issue("year_mismatch", "warning", f"event date {p.event_date} is outside {year}.album"))
    return p


def classify(rel_parts: tuple[str, ...], parent: FolderParse | None = None) -> FolderParse:
    """Classify a folder from its path components relative to the photo root.

    `parent` is the already-computed parse of the parent folder (None for depth 1).
    """
    name = rel_parts[-1]
    if len(rel_parts) == 1:
        m = YEAR_RE.match(name)
        return FolderParse(kind="year", year=int(m["year"])) if m else _ignored("top-level folder isn't YYYY.album")

    assert parent is not None
    if parent.kind == "ignored":
        return FolderParse(kind="ignored", year=parent.year)  # reason is recorded once, on the ancestor
    if CONFLICT_RE.search(name):
        return _ignored("Dropbox conflicted copy; its photos duplicate the original folder", parent.year)
    if parent.kind in ("event", "event_sub"):
        p = FolderParse(kind="event_sub", year=parent.year, state=parent.state, event_name=parent.event_name,
                        event_date=parent.event_date)
        if EVENT_RE.match(name):
            p.issues.append(Issue("nested_event", "warning", "event folder filed inside another event"))
        return p
    if parent.kind in ("highlights", "highlights_sub"):
        return FolderParse(kind="highlights_sub", year=parent.year)

    # parent is a year folder
    if m := HIGHLIGHTS_RE.match(name):
        p = FolderParse(kind="highlights", year=parent.year)
        if m["yy"] and int(m["yy"]) != parent.year % 100:
            p.issues.append(Issue("year_mismatch", "warning", f"'{name}' is inside {parent.year}.album"))
        return p
    return parse_event_name(name, parent.year)
