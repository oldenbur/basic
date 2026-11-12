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
    p = classify(("2015",))
    assert (p.kind, p.year, p.ok) == ("year", 2015, True)


def test_valid_event_under_year():
    p = chain("2015", "150704.CO.fourth of july")
    assert p.kind == "event"
    assert p.event_date == date(2015, 7, 4)
    assert (p.state, p.event_name, p.year) == ("CO", "fourth of july", 2015)
    assert p.ok and not p.issues


def test_event_name_may_contain_dots():
    p = chain("2019", "190212.UT.alta.ski.trip")
    assert p.event_name == "alta.ski.trip" and p.ok


def test_top_level_event_single_level_year():
    p = classify(("990815.WA.rainier",))
    assert p.kind == "event" and p.event_date == date(1999, 8, 15)


def test_year_folder_sets_century():
    p = chain("1998", "980101.CA.new year")
    assert p.event_date == date(1998, 1, 1)


def test_highlights_folder_any_case():
    assert chain("2015", "Highlights").kind == "highlights"
    assert chain("2015", "highlights", "best").kind == "highlights_sub"


def test_event_subfolder_inherits():
    p = chain("2015", "150704.CO.fourth", "raw")
    assert p.kind == "event_sub" and p.state == "CO" and p.event_date == date(2015, 7, 4)


def test_bad_date():
    p = chain("2015", "151399.CO.oops")
    assert "bad_date" in codes(p) and not p.ok


def test_year_mismatch_is_warning():
    p = chain("2015", "141231.CO.nye")
    assert "year_mismatch" in codes(p) and p.ok


def test_unknown_state_is_warning():
    p = chain("2015", "150601.IT.rome")
    assert "unknown_state" in codes(p) and p.ok


def test_lowercase_state_suggests_fix():
    p = chain("2015", "150704.co.fourth")
    assert p.suggested_name == "150704.CO.fourth" and p.ok


@pytest.mark.parametrize(
    "name,suggested",
    [
        ("150704_CO_fourth of july", "150704.CO.fourth of july"),
        ("150704 CO fourth", "150704.CO.fourth"),
        ("20150704.co.fourth", "150704.CO.fourth"),
        ("150704-co-fourth", "150704.CO.fourth"),
    ],
)
def test_wrong_separators_suggest_fix(name, suggested):
    p = chain("2015", name)
    assert "format" in codes(p) and not p.ok
    assert p.suggested_name == suggested


def test_missing_state_has_no_suggestion():
    p = chain("2015", "150704.fourth")
    assert "missing_state" in codes(p) and p.suggested_name is None


def test_unrecognized():
    assert "unrecognized" in codes(chain("2015", "misc stuff"))
    assert "unrecognized" in codes(classify(("Old Scans",)))


def test_loose_two_letter_word_is_not_a_state():
    p = chain("2015", "150704 my trip")
    assert "missing_state" in codes(p) and p.event_name == "my trip" and p.suggested_name is None
