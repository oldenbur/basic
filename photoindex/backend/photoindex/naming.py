"""Classify library folders and validate the yyMMDD.[state].[event] naming convention.

Layout under the photo root:
    YYYY/                       year folder
    YYYY/yyMMDD.ST.event/       event folder (yy must match YYYY)
    YYYY/highlights/            copies of the year's best photos
    yyMMDD.ST.event/            event folder directly under the root (single-level years)
Anything deeper inherits from its event or highlights ancestor.
"""

import re
from dataclasses import dataclass, field
from datetime import date

EVENT_RE = re.compile(r"^(?P<date>\d{6})\.(?P<state>[A-Za-z]{2})\.(?P<event>\S.*)$")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")
HIGHLIGHTS_RE = re.compile(r"^highlights?$", re.IGNORECASE)
# Loose shape used to suggest a fix: 6- or 8-digit date, any separators, optional state.
LOOSE_RE = re.compile(r"^(?P<date>\d{8}|\d{6})[._\-\s]+(?:(?P<state>[A-Za-z]{2})[._\-\s]+)?(?P<event>\S.*)$")

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
    "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split()
)


@dataclass
class Issue:
    code: str
    severity: str  # error | warning
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass
class FolderParse:
    kind: str
    year: int | None = None
    event_date: date | None = None
    state: str | None = None
    event_name: str | None = None
    issues: list[Issue] = field(default_factory=list)
    suggested_name: str | None = None

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


def _expand_year(yy: int, century_hint: int | None) -> int:
    if century_hint is not None:
        return century_hint - century_hint % 100 + yy
    return 2000 + yy if yy <= date.today().year % 100 else 1900 + yy


def _parse_date(digits: str, year_hint: int | None) -> date | None:
    try:
        if len(digits) == 8:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
        return date(_expand_year(int(digits[:2]), year_hint), int(digits[2:4]), int(digits[4:]))
    except ValueError:
        return None


def parse_event_name(name: str, year_hint: int | None = None) -> FolderParse | None:
    """Parse a folder name as an event. Returns None if it doesn't resemble an event at all."""
    m = EVENT_RE.match(name)
    if m:
        p = FolderParse(kind="event", state=m["state"].upper(), event_name=m["event"].strip())
        p.event_date = _parse_date(m["date"], year_hint)
        if p.event_date is None:
            p.issues.append(Issue("bad_date", "error", f"'{m['date']}' is not a valid yyMMDD date"))
        if m["state"] != m["state"].upper():
            p.issues.append(Issue("state_case", "warning", "state code should be upper case"))
            p.suggested_name = f"{m['date']}.{p.state}.{p.event_name}"
        if p.state not in US_STATES:
            p.issues.append(Issue("unknown_state", "warning", f"'{p.state}' is not a US state code"))
        p.year = p.event_date.year if p.event_date else year_hint
        return p

    m = LOOSE_RE.match(name)
    if not m:
        return None
    p = FolderParse(kind="event", event_name=m["event"].strip())
    p.event_date = _parse_date(m["date"], year_hint)
    p.year = p.event_date.year if p.event_date else year_hint
    if p.event_date is None:
        p.issues.append(Issue("bad_date", "error", f"'{m['date']}' is not a valid date"))
    if not m["state"] or m["state"].upper() not in US_STATES:
        # A loose two-letter word ("my trip") is part of the event name, not a state.
        p.event_name = name[len(m["date"]):].lstrip("._- ").strip()
        p.issues.append(Issue("missing_state", "error", "name has no state code"))
        return p
    p.state = m["state"].upper()
    p.issues.append(Issue("format", "error", "expected yyMMDD.ST.event with '.' separators"))
    if p.event_date:
        p.suggested_name = f"{p.event_date:%y%m%d}.{p.state}.{p.event_name}"
    return p


def classify(rel_parts: tuple[str, ...], parent: FolderParse | None = None) -> FolderParse:
    """Classify a folder from its path components relative to the photo root.

    `parent` is the already-computed parse of the parent folder (None for depth 1).
    """
    name = rel_parts[-1]
    depth = len(rel_parts)

    if depth == 1:
        if YEAR_RE.match(name):
            return FolderParse(kind="year", year=int(name))
        ev = parse_event_name(name)
        if ev:
            return ev
        return FolderParse(
            kind="other", issues=[Issue("unrecognized", "error", "top-level folder is neither a year nor an event")]
        )

    assert parent is not None
    if parent.kind in ("event", "event_sub"):
        return FolderParse(kind="event_sub", year=parent.year, state=parent.state, event_name=parent.event_name,
                           event_date=parent.event_date)
    if parent.kind in ("highlights", "highlights_sub"):
        return FolderParse(kind="highlights_sub", year=parent.year)
    if parent.kind != "year":
        return FolderParse(kind="other", year=parent.year)

    if HIGHLIGHTS_RE.match(name):
        return FolderParse(kind="highlights", year=parent.year)
    ev = parse_event_name(name, year_hint=parent.year)
    if ev is None:
        return FolderParse(
            kind="other", year=parent.year,
            issues=[Issue("unrecognized", "error", "folder name doesn't match yyMMDD.ST.event")],
        )
    if ev.event_date and ev.event_date.year != parent.year:
        ev.issues.append(
            Issue("year_mismatch", "warning", f"event date {ev.event_date} is outside year folder {parent.year}")
        )
    return ev
