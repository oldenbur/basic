import numpy as np

from photoindex.albums.events import Print, segment
from photoindex.albums.names import order_key, page_of


def test_order_key_sorts_scanner_names():
    names = ["scan0010.2.jpg", "scan.jpg", "scan0002.1.jpg", "scan0010.10.jpg", "scan0043..JPG", "scan0010.1.jpg",
             "scan0032.4_orig.JPG"]
    assert sorted(names, key=order_key) == ["scan0002.1.jpg", "scan0010.1.jpg", "scan0010.2.jpg", "scan0010.10.jpg",
                                            "scan0032.4_orig.JPG", "scan0043..JPG", "scan.jpg"]
    assert page_of("scan0043..JPG") == 43
    assert page_of("scan.jpg") is None


def _roll(rng, base: int, n: int, size=(3.5, 5.0), page0=1, people=frozenset()):
    """n prints whose colours cluster around one of a few distinct palettes."""
    out = []
    for i in range(n):
        h = np.full(192, 0.2)
        h[base * 30:(base + 1) * 30] += 5 + rng.random(30)
        h += rng.random(192) * 0.3
        out.append(Print(hist=h / h.sum(), size=size, page=page0 + i // 3, people=people))
    return out


def test_segment_finds_roll_changes():
    rng = np.random.default_rng(1)
    prints = _roll(rng, 0, 9) + _roll(rng, 2, 12, page0=4) + _roll(rng, 4, 6, page0=8)
    cuts = segment(prints)
    assert [c.at for c in cuts] == [0, 9, 21]
    assert "colour" in cuts[1].reasons


def test_print_size_change_alone_can_split_similar_colours():
    rng = np.random.default_rng(2)
    prints = _roll(rng, 1, 6) + _roll(rng, 1, 6, size=(4.0, 6.0), page0=3)
    weak = segment(prints, threshold=10)
    assert [c.at for c in weak] == [0]
    cuts = segment(prints, threshold=1.5)
    assert 6 in [c.at for c in cuts]
    assert "print size" in next(c for c in cuts if c.at == 6).reasons


def test_same_people_argue_against_a_break():
    rng = np.random.default_rng(3)
    prints = _roll(rng, 0, 6, people=frozenset({7})) + _roll(rng, 0, 6, page0=3, people=frozenset({7}))
    assert [c.at for c in segment(prints)] == [0]


def test_long_runs_are_split_at_their_strongest_gap():
    rng = np.random.default_rng(4)
    # Two similar-coloured rolls (faded prints) with only a mild shift between them.
    a, b = _roll(rng, 0, 20), _roll(rng, 0, 20, page0=8)
    for p in b:
        p.hist = p.hist * 0.8 + np.roll(p.hist, 30) * 0.2
    cuts = segment(a + b, threshold=1e6)  # no ordinary cut: only the long-run rule can split
    assert [c.at for c in cuts] == [0, 20]
    assert "long run" in cuts[1].reasons


# --- the album stages and API, end to end on a tiny library ----------------------------------------------------

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def album_client(test_env, monkeypatch):
    from conftest import make_jpeg

    from photoindex import config
    from photoindex.worker.pipeline import run_all, run_stage

    for page, k, colour in [(1, 1, (220, 40, 40)), (1, 2, (215, 45, 40)), (2, 1, (225, 35, 45)), (2, 2, (210, 50, 40)),
                            (3, 1, (90, 90, 90)), (3, 2, (95, 95, 95)), (4, 1, (85, 85, 85)), (4, 2, (92, 92, 92))]:
        make_jpeg(test_env / "albums1" / f"scan{page:04d}.{k}.jpg", None, colour)
    make_jpeg(test_env / "albums9" / "scan0001.1.jpg", None)  # not a configured album folder
    monkeypatch.setenv("ALBUM_FOLDERS", "albums1")
    config.get_settings.cache_clear()
    run_all()
    run_stage("album_faces")
    run_stage("album_events")
    from photoindex.api.main import app

    return TestClient(app)


def test_album_prints_are_prepared_but_stay_out_of_the_library(album_client):
    c = album_client
    d = c.get("/api/albums").json()
    assert [(a["album"], a["prints"], a["faces_done"]) for a in d["albums"]] == [("albums1", 8, 8)]
    assert d["faces"] >= 8 and sum(e["size"] for e in d["events"]) == 8
    assert all(p["thumb_url"] for e in d["events"] for p in e["photos"])
    paths = [p["path"] for p in c.post("/api/search", json={"query": {"collapse_bursts": False}}).json()["photos"]]
    assert paths and not any("/albums" in p for p in paths)
    # Album faces have their own table and never reach the People pages.
    from sqlalchemy import func, select

    from photoindex.db import session_scope
    from photoindex.models import AlbumFace, Face, Photo

    with session_scope() as s:
        assert s.scalar(select(func.count()).select_from(Face).join(Photo).where(Photo.album_scan)) == 0
        assert s.scalar(select(func.count()).select_from(AlbumFace)) >= 8


def test_reference_examples(album_client):
    c = album_client
    ref = c.post("/api/albums/refs", json={"kind": "home", "label": "Test house"}).json()
    assert c.post("/api/albums/refs", json={"kind": "home", "label": "Test house"}).status_code == 409
    assert c.post("/api/albums/refs", json={"kind": "castle", "label": "Nope"}).status_code == 422
    prints = [p for e in c.get("/api/albums").json()["events"] for p in e["photos"]]
    assert c.put(f"/api/albums/refs/{ref['id']}/examples/{prints[0]['id']}", json={"status": "confirmed"}).status_code == 200
    assert c.put(f"/api/albums/refs/{ref['id']}/examples/{prints[1]['id']}", json={"status": "rejected"}).status_code == 200
    got = next(r for r in c.get("/api/albums/refs").json() if r["id"] == ref["id"])
    assert [(x["photo_id"], x["status"], x["source"]) for x in got["examples"]] == [
        (prints[0]["id"], "confirmed", "user"), (prints[1]["id"], "rejected", "user")]
    assert c.patch(f"/api/albums/refs/{ref['id']}", json={"start": "1985-12-01", "notes": "brown"}).status_code == 200
    got = next(r for r in c.get("/api/albums/refs").json() if r["id"] == ref["id"])
    assert (got["start"], got["end"], got["notes"]) == ("1985-12-01", None, "brown")
    # Only album prints can be examples.
    library_photo = c.post("/api/search", json={"query": {}}).json()["photos"][0]["id"]
    assert c.put(f"/api/albums/refs/{ref['id']}/examples/{library_photo}", json={"status": "confirmed"}).status_code == 404
    c.delete(f"/api/albums/refs/{ref['id']}/examples/{prints[1]['id']}")
    assert len(next(r for r in c.get("/api/albums/refs").json() if r["id"] == ref["id"])["examples"]) == 1


def test_name_an_album_face_group(album_client):
    c = album_client
    c.post("/api/albums/face-groups/regroup")
    d = c.get("/api/albums/face-groups").json()
    assert d["total"] >= 1 and d["named"] == []
    g = max(d["groups"], key=lambda g: g["size"])
    every = c.get(f"/api/albums/face-groups/{g['id']}/faces").json()
    assert len(every) == g["size"]
    left_out = every[-1]["id"]
    r = c.post(f"/api/albums/face-groups/{g['id']}/assign", json={"name": "Young P", "exclude_face_ids": [left_out]})
    assert r.json()["named"] == g["size"] - 1
    d = c.get("/api/albums/face-groups").json()
    assert [(n["name"], n["count"]) for n in d["named"]] == [("Young P", g["size"] - 1)]
    assert g["id"] not in [x["id"] for x in d["groups"]]
