from datetime import date

import pytest

from photoindex.naming import classify


def chain(*parts: str):
    parse = None
    for i in range(1, len(parts) + 1):
        parse = classify(parts[:i], parse)
    return parse


def codes(p):
    return {i.code for i in p.issues}


def test_year_folder():
    p = classify(("2015.album",))
    assert (p.kind, p.year, p.ok) == ("year", 2015, True)


@pytest.mark.parametrize("name", ["2015", "albums1", "Old Scans", "150704.CO.top level event", "2015.Album"])
def test_other_top_level_folders_are_ignored(name):
    p = classify((name,))
    assert (p.kind, codes(p), p.ok) == ("ignored", {"ignored"}, False)


def test_everything_under_an_ignored_folder_is_ignored_quietly():
    p = chain("albums_slides", "LRO 1948 till")
    assert p.kind == "ignored" and not p.issues


def test_valid_event_under_year():
    p = chain("2015.album", "150704.CO.fourth of july")
    assert p.kind == "event"
    assert p.event_date == date(2015, 7, 4)
    assert (p.state, p.event_name, p.year, p.abroad) == ("CO", "fourth of july", 2015, False)
    assert p.ok and not p.issues


def test_event_name_may_contain_dots():
    p = chain("2019.album", "190212.UT.alta.ski.trip")
    assert p.event_name == "alta.ski.trip" and p.ok


def test_year_folder_sets_century():
    p = chain("1999.album", "990101.CA.new year")
    assert p.event_date == date(1999, 1, 1)


@pytest.mark.parametrize("name", ["15.highlights", "highlights", "Highlights"])
def test_highlights_folder(name):
    assert chain("2015.album", name).kind == "highlights"
    assert chain("2015.album", name, "best").kind == "highlights_sub"


def test_highlights_for_another_year_is_warning():
    p = chain("2015.album", "14.highlights")
    assert p.kind == "highlights" and "year_mismatch" in codes(p)


def test_event_subfolder_inherits():
    p = chain("2015.album", "150704.CO.fourth", "raw")
    assert p.kind == "event_sub" and p.state == "CO" and p.event_date == date(2015, 7, 4)
    assert not chain("2008.album", "080823.MN.Wedding", "amys_camera").issues


@pytest.mark.parametrize("year,name,place", [
    ("2015.album", "150321.Oslo", "Oslo"),
    ("2017.album", "171202.TurksAndCaicos", "TurksAndCaicos"),
    ("2006.album", "060918.Munich old town", "Munich old town"),
])
def test_event_without_state_is_abroad(year, name, place):
    p = chain(year, name)
    assert (p.kind, p.state, p.event_name, p.abroad, p.issues) == ("event", None, place, True, [])


def test_abroad_subfolder_inherits():
    assert chain("2015.album", "150321.Oslo", "day2").abroad


def test_bad_date_is_ignored():
    assert chain("2015.album", "151399.CO.oops").kind == "ignored"
    assert chain("2015.album", "151399.Oslo").kind == "ignored"


def test_year_mismatch_is_warning():
    p = chain("2015.album", "141231.CO.nye")
    assert "year_mismatch" in codes(p) and p.ok


def test_unknown_state_is_warning():
    p = chain("2015.album", "150601.IT.rome")
    assert "unknown_state" in codes(p) and p.ok


def test_lowercase_state_suggests_fix():
    p = chain("2015.album", "150704.co.fourth")
    assert p.suggested_name == "150704.CO.fourth" and p.ok


@pytest.mark.parametrize(
    "name,suggested",
    [
        ("150704_CO_fourth of july", "150704.CO.fourth of july"),
        ("150704 CO fourth", "150704.CO.fourth"),
        ("20150704.co.fourth", "150704.CO.fourth"),
        ("150704-co-fourth", "150704.CO.fourth"),
        ("150704 my trip", None),
        ("misc stuff", None),
        ("101D7000", None),
    ],
)
def test_noncompliant_folders_are_ignored_with_suggestion(name, suggested):
    p = chain("2015.album", name)
    assert (p.kind, codes(p), p.suggested_name) == ("ignored", {"ignored"}, suggested)


def test_conflicted_copy_is_ignored():
    p = chain("2015.album", "150613.CO.BuffaloCreek (Paul Oldenburg's conflicted copy 2026-01-30)")
    assert p.kind == "ignored" and "conflicted copy" in p.issues[0].message


def test_nested_event_is_flagged():
    p = chain("2011.album", "111015.CO.RainbowLakes", "111218.MN.RochXmas")
    assert (p.kind, "nested_event" in codes(p)) == ("event_sub", True)
