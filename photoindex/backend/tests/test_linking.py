from datetime import datetime, timedelta

from photoindex.linking import Candidate, Shot, group_bursts, match_highlights, normalize_stem

T = datetime(2015, 7, 4, 12, 0, 0)


def test_normalize_stem():
    assert normalize_stem("IMG_1234.JPG") == "img_1234"
    assert normalize_stem("IMG_1234-edited.jpg") == "img_1234"
    assert normalize_stem("IMG_1234 (1).jpeg") == "img_1234"
    assert normalize_stem("IMG_1234_HDR copy.jpg") == "img_1234"
    assert normalize_stem("DSC00042.heic") == "dsc00042"


def test_hash_match_wins_across_years():
    o = Candidate(1, "IMG_1.jpg", 2014, "abc")
    h = Candidate(10, "renamed.jpg", 2015, "abc")
    assert match_highlights([h], [o])[10].method == "hash"
    assert match_highlights([h], [o])[10].original_id == 1


def test_reexported_unique_stem_in_same_year():
    o = Candidate(1, "IMG_1234.JPG", 2015, "aaa")
    other_year = Candidate(2, "IMG_1234.JPG", 2016, "bbb")
    h = Candidate(10, "IMG_1234-edited.jpg", 2015, "zzz")
    r = match_highlights([h], [o, other_year])[10]
    assert (r.original_id, r.method) == (1, "stem")


def test_no_match():
    r = match_highlights([Candidate(10, "pano.jpg", 2015, "zzz")], [Candidate(1, "IMG_1.jpg", 2015, "a")])[10]
    assert (r.original_id, r.method) == (None, "none")


def test_ambiguous_stem_requests_exif_then_resolves():
    a = Candidate(1, "IMG_0001.JPG", 2015, "a")
    b = Candidate(2, "IMG_0001.JPG", 2015, "b")  # camera counter wrapped within the year
    h = Candidate(10, "IMG_0001-edited.jpg", 2015, "z")
    r = match_highlights([h], [a, b])[10]
    assert r.method == "ambiguous" and set(r.candidate_ids) == {1, 2}

    a.taken_at, b.taken_at, h.taken_at = T, T + timedelta(days=90), T + timedelta(days=90)
    r = match_highlights([h], [a, b])[10]
    assert (r.original_id, r.method) == (2, "stem_time")


def test_ambiguous_with_full_exif_but_no_time_match():
    a = Candidate(1, "IMG_0001.JPG", 2015, "a", T)
    b = Candidate(2, "IMG_0001.JPG", 2015, "b", T + timedelta(days=1))
    h = Candidate(10, "IMG_0001.JPG", 2015, "z", T + timedelta(days=5))
    r = match_highlights([h], [a, b])[10]
    assert (r.original_id, r.method, r.candidate_ids) == (None, "none", ())


def test_group_bursts():
    shots = [
        Shot(1, T, "X100", 7),
        Shot(2, T + timedelta(seconds=1), "X100", 7),
        Shot(3, T + timedelta(seconds=2.5), "X100", 7),  # 1.5s after #2: same burst
        Shot(4, T + timedelta(seconds=30), "X100", 7),   # isolated
        Shot(5, T + timedelta(seconds=1), "iPhone", 7),  # other camera
        Shot(6, None, "X100", 7),                        # no timestamp
    ]
    assert group_bursts(shots) == {1: 1, 2: 1, 3: 1}
