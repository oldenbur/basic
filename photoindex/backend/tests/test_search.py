"""Search, themes, on-this-day and display copies against the fixture library (see conftest.build_library)."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photoindex import storage
from photoindex.search import folder_terms, split_words
from photoindex.worker.pipeline import run_all


@pytest.mark.parametrize("name,words", [
    ("MooseRiverBWCA", ["moose", "river", "bwca"]),
    ("SMRLodgeSkiing", ["smr", "lodge", "skiing"]),
    ("Twins14mo", ["twins", "14", "mo"]),
    ("Mike&EmilyVisit", ["mike", "emily", "visit"]),
    ("fourth of july", ["fourth", "of", "july"]),
])
def test_split_words(name, words):
    assert split_words(name) == words


def test_folder_terms():
    assert folder_terms("ABasin", "ABasin", "CO", "event") == "a basin abasin co colorado"
    assert folder_terms("160320.Oslo", "Oslo", None, "event") == "oslo abroad"
    assert folder_terms("15.highlights", None, None, "highlights") is None


@pytest.fixture
def client(test_env):
    run_all()
    from photoindex.api.main import app

    c = TestClient(app)
    tree = {f["name"]: f["id"] for f in c.get("/api/tree").json()}
    july = next(f for f in c.get(f"/api/folders/{tree['2015.album']}").json()["children"]
                if f["name"] == "150704.CO.fourth of july")
    oslo = c.get(f"/api/folders/{tree['2016.album']}").json()["children"][0]
    for f in (july, oslo):  # process whole events so there are bursts and an abroad trip to find
        c.put(f"/api/folders/{f['id']}/scope", json={"in_scope": True})
    run_all()
    return c


def names(client, sort="date", **query):
    r = client.post("/api/search", json={"query": query, "sort": sort})
    assert r.status_code == 200, r.text
    return [p["name"] for p in r.json()["photos"]]


def test_search_filters(client):
    # Processing set: July event (4, IMG_0002/0003 a burst), alta IMG_0001, unmatched pano, Oslo.
    assert names(client) == ["IMG_0001.JPG", "IMG_0002.JPG", "pano.jpg", "IMG_0001.JPG", "IMG_0004.JPG",
                             "IMG_8000.JPG"]  # 7 photos, burst IMG_0002/0003 collapsed to one
    assert len(names(client, collapse_bursts=False)) == 7
    assert names(client, text="fourth") == ["IMG_0001.JPG", "IMG_0002.JPG", "IMG_0004.JPG"]
    assert names(client, text="july fourth") == names(client, text="fourth")  # all words must match
    assert names(client, text="alta | oslo") == ["IMG_0001.JPG", "IMG_8000.JPG"]
    assert names(client, text="colorado") == names(client, text="fourth")  # state name
    assert names(client, text="fourht of jully") == []  # short words get no typo tolerance...
    assert names(client, text="fourht") == []
    assert len(names(client, text="fourthh")) == 3  # ...longer ones do
    assert names(client, states=["abroad"]) == ["IMG_8000.JPG"]
    assert names(client, states=["UT", "abroad"]) == ["IMG_0001.JPG", "IMG_8000.JPG"]
    assert names(client, months=[9]) == ["IMG_0004.JPG"]
    assert names(client, year_from=2016) == ["IMG_8000.JPG"]
    assert names(client, has_gps=True) == ["IMG_0001.JPG"]
    assert names(client, highlights_only=True) == ["IMG_0003.JPG", "pano.jpg", "IMG_0001.JPG"]


def test_burst_keeps_the_highlighted_shot_when_filtering(client):
    # IMG_0002/0003 are a burst; with bursts collapsed the earliest shot represents it.
    assert "IMG_0002.JPG" in names(client) and "IMG_0003.JPG" not in names(client)


def test_facets_and_total(client):
    r = client.post("/api/search", json={"with_facets": True}).json()
    assert r["total"] == 6
    f = r["facets"]
    assert {x["value"]: x["count"] for x in f["year"]} == {2015: 5, 2016: 1}
    assert {x["value"]: x["count"] for x in f["state"]} == {"CO": 3, "UT": 1, "abroad": 1}
    assert {x["value"] for x in f["month"]} == {3, 7, 8, 9}
    # a facet ignores its own filter, so other states stay visible to add
    r = client.post("/api/search", json={"query": {"states": ["CO"]}, "with_facets": True}).json()
    assert r["total"] == 3
    assert {x["value"]: x["count"] for x in r["facets"]["state"]} == {"CO": 3, "UT": 1, "abroad": 1}
    assert {x["value"]: x["count"] for x in r["facets"]["year"]} == {2015: 3}


def test_sorts_are_stable_per_seed_and_keep_events_together(client):
    def ids(sort, seed):
        return [p["id"] for p in client.post("/api/search", json={"sort": sort, "seed": seed}).json()["photos"]]

    assert ids("shuffle", 1) == ids("shuffle", 1)
    assert sorted(ids("shuffle", 1)) == sorted(ids("date", 0))
    for seed in range(5):
        photos = client.post("/api/search", json={"sort": "event_shuffle", "seed": seed}).json()["photos"]
        events = [p["event_folder_id"] for p in photos]
        # each event's photos are contiguous, in date order
        assert len({e for i, e in enumerate(events) if i == 0 or events[i - 1] != e}) == len(set(events))


def test_paging(client):
    first = client.post("/api/search", json={"limit": 4}).json()
    rest = client.post("/api/search", json={"offset": 4, "limit": 4}).json()
    assert first["has_more"] and not rest["has_more"] and "total" not in rest
    assert len(first["photos"]) + len(rest["photos"]) == first["total"]


def test_on_this_day(client):
    photos = client.get("/api/onthisday", params={"month": 7, "day": 4}).json()
    assert [p["name"] for p in photos] == ["IMG_0003.JPG"]  # highlights only; widens to +/-3 days when sparse
    assert client.get("/api/onthisday", params={"month": 2, "day": 30}).status_code == 422


def test_display_copy_made_once_and_prefers_edited_highlight(client):
    alta = next(p for p in client.post("/api/search", json={"query": {"text": "alta"}}).json()["photos"])
    r = client.get(alta["display_url"], follow_redirects=False)
    assert r.status_code == 307
    key = storage.display_key(alta["id"])
    data = storage._client().get_object(Bucket="photoindex-test", Key=key)["Body"].read()
    with Image.open(io.BytesIO(data)) as im:
        # alta's original is (250,250,250); the re-exported highlight copy is (240,240,240), and that wins
        assert im.getpixel((5, 5))[0] in range(236, 245)
    detail = client.get(f"/api/photos/{alta['id']}").json()
    assert detail["display_url"] == alta["display_url"]
    assert client.get(alta["display_url"], follow_redirects=False).status_code == 307  # served from S3 now


def test_themes_crud_and_prepare(client):
    r = client.post("/api/themes", json={"name": "July", "query": {"text": "fourth"}})
    assert r.status_code == 201
    t = r.json()
    assert (t["count"], t["prepared"], t["sort"]) == (3, 0, "event_shuffle")
    assert t["cover_url"]
    assert client.post("/api/themes", json={"name": "July"}).status_code == 409

    assert client.post(f"/api/themes/{t['id']}/prepare").status_code == 202  # runs before TestClient returns
    assert client.get(f"/api/themes/{t['id']}").json()["prepared"] == 3

    upd = client.put(f"/api/themes/{t['id']}", json={"name": "Utah", "query": {"states": ["UT"]}, "sort": "date"})
    assert (upd.json()["name"], upd.json()["count"]) == ("Utah", 1)
    assert [x["name"] for x in client.get("/api/themes").json()] == ["Utah"]
    assert client.delete(f"/api/themes/{t['id']}").status_code == 204
    assert client.get("/api/themes").json() == []


def test_seed_themes(test_env):
    from photoindex.db import session_scope
    from photoindex.themes import STARTER_THEMES, seed

    with session_scope() as s:
        assert len(seed(s)) == len(STARTER_THEMES)
        assert seed(s) == []


def test_display_survives_a_failing_batch(client, monkeypatch):
    from photoindex import display
    from photoindex.db import session_scope
    from photoindex.sources import get_source

    source = get_source()
    real = source.thumbnails
    ids = [p["id"] for p in client.post("/api/search", json={}).json()["photos"]]

    def flaky(paths, size):
        if len(paths) > 1:
            raise RuntimeError("Dropbox 500")
        if "img_0004" in paths[0]:
            raise RuntimeError("can't render this one")
        return real(paths, size)

    monkeypatch.setattr(source, "thumbnails", flaky)
    with session_scope() as s:
        made = display.render(s, source, ids)
    assert sum(1 for k in made.values() if k) == len(ids) - 1  # everything but IMG_0004
