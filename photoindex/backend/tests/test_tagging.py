"""AI tagging: vocabulary, requests, pilot -> compare -> choose -> backfill, spend cap, retries, applying answers
(tags, place, rotation), your tag edits, the tag vocabulary page, and search on tags. Uses FakeBatches (conftest)."""

import base64
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from photoindex import storage
from photoindex.rotation import rotate_box
from photoindex.tagging import pricing
from photoindex.tagging.vocab import normalize, tags_from
from photoindex.worker.pipeline import run_all, run_stage

OPUS, HAIKU = "claude-opus-5-5", "claude-haiku-5-5"


@pytest.mark.parametrize("cat,raw,want", [
    ("activity", "Downhill Skiing", "skiing"),
    ("activity", "trick or treating", "trick-or-treating"),
    ("object", "Sleds", "sled"),
    ("object", "fire", "campfire"),
    ("object", "fireworks", "fireworks"),
    ("object", "birthday cakes", "cake"),
    ("animal", "Puppies", "dog"),
    ("animal", "geese", "goose"),
    ("gear", "Tents", "tent"),
    ("gear", "trekking poles", "trekking pole"),
    ("vehicle", "Pickup", "pickup truck"),
    ("object", "  ", None),
])
def test_normalize(cat, raw, want):
    assert normalize(cat, raw) == want


def test_tags_from_answer():
    tags = tags_from({"scene": "Ski Slopes", "activities": ["skiing", "Downhill skiing"], "objects": ["Sleds"],
                      "vehicles": [{"type": "SUV", "make_model": "Subaru Outback", "color": "green"}],
                      "landmarks": ["Longs Peak", "longs peak"], "animals": [], "camping_gear": []})
    assert tags == [("scene", "ski slopes"), ("activity", "skiing"), ("object", "sled"), ("landmark", "Longs Peak"),
                    ("vehicle", "suv"), ("vehicle", "subaru outback")]


def test_rotate_box_round_trips():
    box = (0.1, 0.2, 0.3, 0.15)
    b = box
    for _ in range(4):
        b = rotate_box(*b, 90)
    assert b == pytest.approx(box)
    assert rotate_box(*rotate_box(*box, 90), 270) == pytest.approx(box)
    assert rotate_box(*box, 90) == pytest.approx((1 - 0.35, 0.1, 0.15, 0.3))


def test_cost():
    # Opus batch: (1200*4 + 1500*0.2 + 300*20) / 1e6 / 2
    assert pricing.cost(OPUS, 1200, 300, cache_read=1500) == pytest.approx(0.00555)
    assert pricing.cost(HAIKU, 1200, 300, batch=False) == pytest.approx(0.00027)


@pytest.fixture
def client(test_env, monkeypatch):
    """Faces and tags for every photo in the processing set (not only highlights), with the July and Oslo events
    added, so there's a burst (a follower), an abroad trip and photos with and without GPS."""
    from photoindex.worker.stages import faces

    monkeypatch.setattr(faces, "SCOPE", "in_processing_set AND NOT ignored")
    run_all()
    from photoindex.api.main import app

    c = TestClient(app)
    tree = {f["name"]: f["id"] for f in c.get("/api/tree").json()}
    july = next(f for f in c.get(f"/api/folders/{tree['2015.album']}").json()["children"]
                if f["name"] == "150704.CO.fourth of july")
    oslo = c.get(f"/api/folders/{tree['2016.album']}").json()["children"][0]
    for f in (july, oslo):
        c.put(f"/api/folders/{f['id']}/scope", json={"in_scope": True})
    run_all()
    return c


def photo_ids(client, **query) -> dict[str, int]:
    photos = client.post("/api/search", json={"query": query, "sort": "date", "collapse_bursts": False}).json()["photos"]
    return {f"{p['event_name']}/{p['name']}": p["id"] for p in photos}


def names(client, sort="date", **query) -> list[str]:
    r = client.post("/api/search", json={"query": query, "sort": sort})
    assert r.status_code == 200, r.text
    return [p["name"] for p in r.json()["photos"]]


def wait_pilot(client):
    for _ in range(200):
        s = client.get("/api/tagging").json()
        if not s["pilot_starting"]:
            return s
        time.sleep(0.05)
    raise AssertionError("pilot never started")


def test_places_from_gps_and_folder(client):
    from photoindex.db import session_scope
    from photoindex.models import Photo

    with session_scope() as s:
        rows = {p.name + "@" + str(p.folder_id): p for p in s.scalars(select(Photo).where(Photo.in_processing_set))}
        by_name = {}
        for p in rows.values():
            by_name.setdefault(p.name, []).append(p)
        gps = next(p for p in by_name["IMG_0001.JPG"] if p.lat is not None)
        assert (gps.place_source, gps.place_country) == ("gps", "United States")
        alta = next(p for p in by_name["IMG_0001.JPG"] if p.lat is None)
        assert (alta.place_source, alta.place_region, alta.place_city) == ("folder", "Utah", None)
        oslo = by_name["IMG_8000.JPG"][0]
        assert oslo.place_source is None  # abroad without GPS: left for the AI


def test_pilot_compare_choose(client, fake_anthropic):
    assert client.get("/api/tagging").json()["state"] == "not_started"
    r = client.post("/api/tagging/pilot", json={"size": 50})
    assert r.status_code == 202, r.text
    s = wait_pilot(client)
    assert s["pilot_error"] is None and s["state"] == "pilot"
    assert len(fake_anthropic.batches) == 3
    reqs = next(iter(fake_anthropic.batches.values()))
    # 7 photos in scope. July's IMG_0002/0003 are a burst, and IMG_0001 looks the same (the fixture photos share
    # a pattern, so their phashes match): one of the three is sent.
    assert len(reqs) == 5
    assert client.get("/api/tagging").json()["counts"] == {"pending": 5, "follower": 2}

    # What one request looks like
    by_model = {b[0]["params"]["model"]: b for b in fake_anthropic.batches.values()}
    p = by_model[OPUS][0]["params"]
    assert p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert p["output_config"]["effort"] == "low" and p["output_config"]["format"]["type"] == "json_schema"
    assert by_model[HAIKU][0]["params"]["thinking"] == {"type": "disabled"}
    img = p["messages"][0]["content"][0]["source"]
    with Image.open(io.BytesIO(base64.b64decode(img["data"]))) as im:
        assert max(im.size) <= 1024
    ctx = {r["custom_id"]: r["params"]["messages"][0]["content"][1]["text"] for r in by_model[OPUS]}
    july = next(t for t in ctx.values() if "fourth of july" in t)
    assert "Event: fourth of july | CO, USA | folder date 2015-07-04" in july
    assert "Taken: 2015-07-04" in july and "People recognised" in july
    assert any("outside the US" in t for t in ctx.values())
    assert any("GPS: 39.0000, -105.0000 (near" in t for t in ctx.values())

    # Batches still running: nothing collected
    fake_anthropic.hold = True
    assert run_stage("tag")["poll"] == {"running": 3}
    fake_anthropic.hold = False
    out = run_stage("tag")
    assert out["poll"]["batches_ended"] == 3 and out["poll"]["done"] == 15

    # Pilot answers are kept for comparison, not applied
    assert client.get("/api/tagging").json()["counts"] == {"pending": 5, "follower": 2}
    assert names(client, tags=["activity:skiing"]) == []
    pilot = client.get("/api/tagging/pilot").json()
    assert (len(pilot["photos"]), pilot["running"], pilot["voted"]) == (5, 0, 0)
    assert {m["model"] for m in pilot["models"]} == set(pricing.MODELS)
    opus = next(m for m in pilot["models"] if m["model"] == OPUS)
    assert opus["per_photo"] == pytest.approx(pricing.cost(OPUS, 1200, 300, cache_read=1500))
    assert opus["estimate_all"] == pytest.approx(opus["per_photo"] * 7)

    # Vote: Opus best on one photo, one Haiku tag flagged wrong
    first = pilot["photos"][0]
    ans = {a["model"]: a for a in first["answers"]}
    flag = ans[HAIKU]["tags"][0]
    r = client.post(f"/api/tagging/pilot/{first['photo_id']}/vote",
                    json={"best_id": ans[OPUS]["id"], "flags": {ans[HAIKU]["id"]: [flag]}})
    assert r.status_code == 200
    pilot = client.get("/api/tagging/pilot").json()
    tally = {m["model"]: (m["best"], m["flagged"]) for m in pilot["models"]}
    assert tally[OPUS] == (1, 0) and tally[HAIKU] == (0, 1) and pilot["voted"] == 1

    # Choose Opus: its answers apply to the 5 sent photos and the 2 that copy one of them
    r = client.post("/api/tagging/choose", json={"model": OPUS})
    assert r.json()["applied"] == 5
    st = client.get("/api/tagging").json()
    assert st["counts"] == {"done": 5, "follower": 2} and st["state"] == "done"
    assert st["config"]["model"] == OPUS

    ids = photo_ids(client)
    assert names(client, tags=["activity:skiing"], collapse_bursts=False) == [
        "IMG_0001.JPG", "IMG_0002.JPG", "IMG_0003.JPG", "pano.jpg", "IMG_8000.JPG"]  # colourful ones, followers too
    assert names(client, text="skis") == names(client, tags=["activity:skiing"])  # stemmed caption/tag words
    assert names(client, text="jeep") == names(client, tags=["activity:skiing"])
    assert names(client, text="tent") == ["IMG_0001.JPG", "IMG_0004.JPG"]  # the grey ones: alta, July's last
    assert names(client, min_score=8) == names(client, tags=["activity:skiing"])
    assert set(names(client, sort="best")[-2:]) == {"IMG_0001.JPG", "IMG_0004.JPG"}
    facets = client.post("/api/search", json={"with_facets": True}).json()["facets"]
    assert {f["label"]: f["count"] for f in facets["activity"]} == {"skiing": 4, "hiking": 2}  # bursts collapsed
    assert {f["label"] for f in facets["vehicle"]} == {"pickup truck", "jeep wrangler"}
    # picking a tag keeps the rest of its category visible to add
    facets = client.post("/api/search", json={"query": {"tags": ["activity:hiking"]}, "with_facets": True}).json()["facets"]
    assert {f["label"]: f["count"] for f in facets["activity"]} == {"skiing": 4, "hiking": 2}
    assert {f["label"] for f in facets["gear"]} == {"tent"}

    # Place: Oslo from the AI (medium confidence); Nederland was only a low-confidence guess, so not used
    oslo = next(v for k, v in ids.items() if k.endswith("IMG_8000.JPG"))
    info = client.get(f"/api/photos/{oslo}/ai").json()
    assert info["place"] == {"country": "Norway", "region": "Oslo", "city": "Oslo", "source": "ai"}
    assert names(client, countries=["Norway"]) == ["IMG_8000.JPG"]
    assert info["model"] == "Opus 5.5" and info["caption"] == "Kids skiing"
    assert {t["key"] for t in info["tags"]} >= {"activity:skiing", "animal:dog", "landmark:Eldora"}

    # The teal pano was "sideways": turned 90 degrees, faces moved and looked for again
    pano = next(v for k, v in ids.items() if k.endswith("pano.jpg"))
    detail = client.get(f"/api/photos/{pano}").json()
    assert detail["rotation"] == 90 and detail["thumb_url"]
    from photoindex.db import session_scope
    from photoindex.models import Photo

    with session_scope() as s:
        p = s.get(Photo, pano)
        assert p.thumb_key.endswith("-r90.jpg") and p.display_key.endswith("-r90.jpg")
        with Image.open(io.BytesIO(storage.get_bytes(p.thumb_key))) as im:
            assert im.height > im.width  # was landscape
        assert p.face_status == "done"  # re-detected by the background task after choose


def test_backfill_cap_and_retries(client, fake_anthropic):
    from photoindex.db import session_scope
    from photoindex.tagging import batches

    ids = photo_ids(client)
    oslo = next(v for k, v in ids.items() if k.endswith("IMG_8000.JPG"))
    pano = next(v for k, v in ids.items() if k.endswith("pano.jpg"))
    fake_anthropic.fail_once.add(oslo)
    fake_anthropic.invalid.add(pano)

    with session_scope() as s:
        batches.set_config(s, daily_cap=0.01)
    client.post("/api/tagging/choose", json={"model": OPUS})  # no pilot: nothing to apply, backfill starts
    assert run_stage("tag")["waiting"] == "daily cap"
    assert client.get("/api/tagging").json()["state"] == "waiting_cap"
    assert fake_anthropic.batches == {}

    client.put("/api/tagging/settings", json={"daily_cap": 25})
    out = run_stage("tag")
    assert out["submitted"] == 5 and out["poll"] == {}
    assert client.get("/api/tagging").json()["counts"] == {"queued": 5, "follower": 2}
    out = run_stage("tag")  # collects, then resubmits the photo that failed
    assert out["poll"]["done"] == 3 and out["poll"]["error"] == 2
    assert out["submitted"] == 1
    st = client.get("/api/tagging").json()
    assert st["counts"] == {"done": 3, "follower": 2, "queued": 1, "error": 1}
    out = run_stage("tag")
    assert out["poll"]["done"] == 1 and "submitted" not in out
    st = client.get("/api/tagging").json()
    assert st["counts"] == {"done": 4, "follower": 2, "error": 1}  # the invalid one isn't retried
    assert st["state"] == "done"
    assert [r["kind"] for r in st["runs"]] == ["backfill", "backfill"]
    # only answered requests cost anything
    assert st["spent_today"] == pytest.approx(4 * pricing.cost(OPUS, 1200, 300, cache_read=1500))

    with session_scope() as s:
        batches.set_config(s, paused=True)
    assert client.get("/api/tagging").json()["state"] == "paused"


def test_refusal_is_not_retried(client, fake_anthropic):
    ids = photo_ids(client)
    pano = next(v for k, v in ids.items() if k.endswith("pano.jpg"))
    fake_anthropic.refuse.add(pano)
    client.post("/api/tagging/choose", json={"model": HAIKU})
    run_stage("tag")
    out = run_stage("tag")
    assert out["poll"]["refused"] == 1
    assert client.get("/api/tagging").json()["counts"]["error"] == 1


def test_your_tag_edits_survive_retagging(client, fake_anthropic):
    from photoindex.db import session_scope
    from photoindex.models import Photo, PhotoAI
    from photoindex.tagging.apply import apply

    client.post("/api/tagging/choose", json={"model": OPUS})
    run_stage("tag")
    run_stage("tag")
    oslo = next(v for k, v in photo_ids(client).items() if k.endswith("IMG_8000.JPG"))
    info = client.get(f"/api/photos/{oslo}/ai").json()
    dog = next(t for t in info["tags"] if t["key"] == "animal:dog")
    r = client.patch(f"/api/photos/{oslo}/tags", json={"add": ["activity:Sightseeing tour"], "remove": [dog["id"]]})
    assert r.status_code == 200, r.text
    keys = {t["key"] for t in r.json()["tags"]}
    assert "activity:sightseeing" in keys and "animal:dog" not in keys
    assert names(client, tags=["animal:dog"]) == ["IMG_0001.JPG", "IMG_0002.JPG", "pano.jpg"]
    assert names(client, text="sightseeing") == ["IMG_8000.JPG"]

    with session_scope() as s:  # the same answer applied again (e.g. re-tagging)
        p = s.get(Photo, oslo)
        apply(s, p, s.get(PhotoAI, p.ai_id))
    keys = {t["key"] for t in client.get(f"/api/photos/{oslo}/ai").json()["tags"]}
    assert "activity:sightseeing" in keys and "animal:dog" not in keys
    assert client.patch(f"/api/photos/{oslo}/tags", json={"add": ["bogus:thing"]}).status_code == 422


def test_tag_vocabulary_merge_rename_hide(client, fake_anthropic):
    client.post("/api/tagging/choose", json={"model": OPUS})
    run_stage("tag")
    run_stage("tag")
    tags = {t["key"]: t for t in client.get("/api/tags").json()}
    assert tags["activity:skiing"]["count"] == 5 and tags["gear:tent"]["count"] == 2

    # Rename sled -> toboggan (normalised); merging across kinds of tag isn't allowed
    sled = tags["object:sled"]
    r = client.patch(f"/api/tags/{sled['id']}", json={"value": "Toboggans"})
    assert r.json()["value"] == "toboggan"
    assert names(client, text="toboggan") == names(client, tags=["activity:skiing"])
    bad = client.patch(f"/api/tags/{sled['id']}", json={"merge_into_id": tags["activity:hiking"]["id"]})
    assert bad.status_code == 422

    # Renaming onto an existing tag merges them; future answers for the old name land on the new one
    fire = tags["object:campfire"]
    r = client.patch(f"/api/tags/{fire['id']}", json={"value": "waterfall"})
    assert r.json()["key"] == "object:waterfall" and r.json()["count"] == 7
    assert "object:campfire" not in {t["key"] for t in client.get("/api/tags").json()}
    from photoindex.db import session_scope
    from photoindex.tagging.apply import resolve_tag

    with session_scope() as s:
        assert resolve_tag(s, "object", "campfire").value == "waterfall"

    # Hidden tags drop out of facets, photo details and text search
    r = client.patch(f"/api/tags/{tags['gear:tent']['id']}", json={"hidden": True})
    assert r.json()["hidden"]
    facets = client.post("/api/search", json={"with_facets": True}).json()["facets"]
    assert facets["gear"] == []
    assert names(client, text="tent") == []


def test_rotation_moves_faces_and_redetecting_keeps_names(client):
    from photoindex.db import session_scope
    from photoindex.models import Face, Person, Photo
    from photoindex.rotation import set_rotation

    pid = next(v for k, v in photo_ids(client).items() if k.endswith("IMG_0004.JPG"))
    with session_scope() as s:
        faces = s.scalars(select(Face).where(Face.photo_id == pid).order_by(Face.x)).all()
        assert len(faces) == 2
        pat = Person(name="Pat")
        s.add(pat)
        s.flush()
        faces[0].person_id, faces[0].assigned_by = pat.id, "user"
        faces[1].rejected_person_ids = [pat.id]
        pat.cover_face_id = faces[0].id
        s.commit()
        pat_id = pat.id

        # Detecting again in place: names, rejections and the cover move to the new face rows
        s.get(Photo, pid).face_status = "pending"
        s.commit()
    run_stage("faces")
    with session_scope() as s:
        faces = s.scalars(select(Face).where(Face.photo_id == pid).order_by(Face.x)).all()
        assert [f.person_id for f in faces] == [pat_id, None]
        assert faces[1].rejected_person_ids == [pat_id]
        assert s.get(Person, pat_id).cover_face_id == faces[0].id
        before = [(f.x, f.y, f.w, f.h) for f in faces]

        # Turning the photo: copies rotated under new keys, boxes moved with the image, faces queued again
        p = s.get(Photo, pid)
        old_thumb = p.thumb_key
        assert set_rotation(s, p, 90) and not set_rotation(s, p, 90)
        assert p.thumb_key == storage.thumb_key(pid, 90) != old_thumb
        with Image.open(io.BytesIO(storage.get_bytes(p.thumb_key))) as im:
            assert im.height > im.width
        after = [(f.x, f.y, f.w, f.h) for f in s.scalars(select(Face).where(Face.photo_id == pid).order_by(Face.id))]
        assert len(after) == 2
        assert all(any(a == pytest.approx(rotate_box(*b, 90)) for b in before) for a in after)
        assert p.face_status == "pending"

    r = client.put(f"/api/photos/{pid}/rotation", json={"rotation": 0})
    assert r.status_code == 200 and r.json()["rotation"] == 0
    assert client.put(f"/api/photos/{pid}/rotation", json={"rotation": 45}).status_code == 422
    with session_scope() as s:
        p = s.get(Photo, pid)
        assert p.thumb_key == storage.thumb_key(pid) and p.face_status == "done"  # re-detected in the background
        # back where they started, so the name found its face again
        assert [f.person_id for f in s.scalars(select(Face).where(Face.photo_id == pid).order_by(Face.x))] == [pat_id, None]
