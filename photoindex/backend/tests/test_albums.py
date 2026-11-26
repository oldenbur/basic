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


class FakeDatingBatches:
    """Answers each event request with one date per print; print 2 of every event is flagged as a different occasion."""

    def __init__(self):
        self.batches: dict[str, list[dict]] = {}

    def create(self, requests):
        from types import SimpleNamespace

        bid = f"msgbatch_d{len(self.batches) + 1}"
        self.batches[bid] = list(requests)
        return SimpleNamespace(id=bid, processing_status="in_progress")

    def retrieve(self, batch_id):
        from types import SimpleNamespace

        return SimpleNamespace(id=batch_id, processing_status="ended")

    def results(self, batch_id):
        import json
        from types import SimpleNamespace as NS

        for req in self.batches[batch_id]:
            texts = [b["text"] for b in req["params"]["messages"][0]["content"] if b["type"] == "text"]
            n = sum(t.startswith("Print ") for t in texts)
            answer = {"event": {"summary": "Christmas", "best": "1984-12", "earliest": "1984-11", "latest": "1985-01",
                                "confidence": "medium", "clues": "Joe looks about 7 months old"},
                      "prints": [{"print": i, "best": "1984-12", "earliest": "1985-01", "latest": "1984-11",
                                  "confidence": "medium", "reference": "Test house" if i == 1 else "",
                                  "ages": [{"name": "Joe", "age": 0.6}], "different_occasion": i == 2,
                                  "caption": f"print {i}"} for i in range(1, n + 1)]
                      + [{"print": n + 5, "best": "1984-12", "earliest": "", "latest": "", "confidence": "low",
                          "reference": "", "ages": [], "different_occasion": False, "caption": "out of range"}]}
            msg = NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(answer))],
                     usage=NS(input_tokens=4000, output_tokens=2500, cache_read_input_tokens=12000,
                              cache_creation_input_tokens=0))
            yield NS(custom_id=req["custom_id"], result=NS(type="succeeded", message=msg))


def test_dating_pilot_round_trip(album_client, monkeypatch):
    from types import SimpleNamespace

    from sqlalchemy import select

    from photoindex.albums import dating
    from photoindex.db import session_scope
    from photoindex.models import AlbumDateAnswer, AlbumPrintDate
    from photoindex.tagging import client

    fake = FakeDatingBatches()
    monkeypatch.setattr(client, "get_client", lambda: SimpleNamespace(messages=SimpleNamespace(batches=fake)))
    c = album_client
    ref = c.post("/api/albums/refs", json={"kind": "home", "label": "Test house", "start": "1983-12-01"}).json()
    first = c.get("/api/albums").json()["events"][0]["photos"][0]["id"]
    c.put(f"/api/albums/refs/{ref['id']}/examples/{first}", json={"status": "confirmed"})

    with session_scope() as s:
        events = dating.pilot_events(s, n=2)
        assert events
        try:
            dating.submit(s, "pilot", events, max_usd=0.0001)
            raise AssertionError("expected the spend limit to stop it")
        except dating.SpendLimit:
            pass
        run = dating.submit(s, "pilot", events, max_usd=5)
        sent = fake.batches[run.batch_id]
        params = sent[0]["params"]
        assert params["model"] == "claude-opus-5-5" and params["output_config"]["effort"] == "medium"
        content = params["messages"][0]["content"]
        assert any(b.get("cache_control") for b in content)  # the shared reference prefix is cached
        assert any("Test house" in b.get("text", "") for b in content)
        assert "Rico (Eric Oldenburg): born 1978-04" in params["system"][0]["text"]
        assert dating.poll(s)["done"] == len(events)
        answers = s.scalars(select(AlbumDateAnswer)).all()
        assert all(a.status == "done" and a.cost_usd > 0 for a in answers)
        rows = s.scalars(select(AlbumPrintDate)).all()
        assert len(rows) == sum(len(a.photo_ids) for a in answers)  # the out-of-range print is dropped
        r = next(r for r in rows if r.photo_id == answers[0].photo_ids[0])
        assert (str(r.best), str(r.earliest), str(r.latest)) == ("1984-12-01", "1984-11-01", "1985-01-01")  # swapped
        assert r.ref_label == "Test house" and r.ages == [{"name": "Joe", "age": 0.6}]
        assert any(r.different_occasion for r in rows)
        assert dating.poll(s) == {}  # nothing left to collect


def test_placement_smoothing():
    from photoindex.albums.placement import EventIn, PrintIn, place, to_date, to_index

    m = lambda y, mo: to_index(date(y, mo, 1))  # noqa: E731
    evs = [
        EventIn(1, [PrintIn(1, m(1984, 10), m(1984, 9), m(1984, 11), "high"),
                    PrintIn(2, m(1984, 10), m(1984, 9), m(1984, 11), "medium")], "high"),
        # low confidence, guessed too late, but its own range allows the neighbours' span
        EventIn(2, [PrintIn(3, m(1987, 6), m(1983, 1), m(1990, 1), "low"),
                    PrintIn(4, None),  # skipped by the model: takes the event's month
                    PrintIn(5, m(1960, 6), m(1955, 1), m(1965, 1), "low", odd=True)], "low"),
        EventIn(3, [PrintIn(6, m(1985, 5), m(1985, 5), m(1985, 5), "high")], "high"),
        # a print matched to a reference whose dates disagree is kept inside them
        EventIn(4, [PrintIn(7, m(1980, 1), None, None, "medium", ref=(m(1985, 12), None))], "medium"),
    ]
    out = place(evs)
    assert to_date(out[3].month) == date(1985, 5, 1) and out[3].source == "neighbours"
    assert out[4].month == out[3].month
    assert to_date(out[5].month) == date(1960, 6, 1)  # a different occasion keeps its own date
    assert to_date(out[1].month) == date(1984, 10, 1) and out[1].source == "model"
    assert to_date(out[7].month) == date(1985, 12, 1)


from datetime import date  # noqa: E402


def test_split_move_and_edit_events(album_client, monkeypatch):
    from types import SimpleNamespace

    from photoindex.albums import dating
    from photoindex.db import session_scope
    from photoindex.tagging import client

    fake = FakeDatingBatches()
    monkeypatch.setattr(client, "get_client", lambda: SimpleNamespace(messages=SimpleNamespace(batches=fake)))
    c = album_client
    with session_scope() as s:
        dating.submit(s, "pilot", dating.undated_events(s), max_usd=5)
        dating.poll(s)
    assert c.post("/api/albums/placements/run").status_code == 200
    events = c.get("/api/albums/placements", params={"view": "all"}).json()["events"]
    big = max(events, key=lambda e: len(e["prints"]))
    assert len(big["prints"]) >= 2 and all(p["month"] == "1984-12" for p in big["prints"])
    moved = [big["prints"][-1]["photo_id"]]

    r = c.post("/api/albums/placements/move", json={"photo_ids": moved, "to": "new"}).json()
    key = r["to"]
    assert key.startswith("g")
    events = {e["key"]: e for e in c.get("/api/albums/placements", params={"view": "all"}).json()["events"]}
    assert [p["photo_id"] for p in events[key]["prints"]] == moved
    assert moved[0] not in [p["photo_id"] for p in events[big["key"]]["prints"]]
    assert events[key]["prev"] == big["key"]  # it sits after the event it came from

    # a month and a decision of its own, kept across reruns
    c.put(f"/api/albums/placements/events/{key}", json={"month": "1996-07", "status": "skip"})
    c.post("/api/albums/placements/run")
    e = {e["key"]: e for e in c.get("/api/albums/placements", params={"view": "all"}).json()["events"]}[key]
    assert e["prints"][0]["month"] == "1996-07" and e["prints"][0]["status"] == "skip" and e["decision"] == "skip"
    c.put(f"/api/albums/placements/events/{key}", json={"status": "auto"})
    e = {e["key"]: e for e in c.get("/api/albums/placements").json()["events"]}[key]
    assert e["decision"] == "undecided"  # 1996 and nobody recognised: back on the review list

    # moving it back where it was dated drops the empty group
    assert c.post("/api/albums/placements/move", json={"photo_ids": moved, "to": big["key"]}).status_code == 200
    keys = [e["key"] for e in c.get("/api/albums/placements", params={"view": "all"}).json()["events"]]
    assert key not in keys
    assert c.post("/api/albums/placements/move", json={"photo_ids": moved, "to": "g999"}).status_code == 404
