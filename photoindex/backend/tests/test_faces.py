"""Faces: grouping and matching logic, the faces stage, and the people API (with the fake engine in conftest)."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from photoindex import storage
from photoindex.faces.cluster import AUTO_ASSIGN, SUGGEST, cluster, match, quality
from photoindex.worker.pipeline import run_all


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def test_match_uses_nearest_faces_and_respects_rejections():
    rng = np.random.default_rng(0)
    a, b = unit(rng.normal(size=(2, 512)))
    # "a" as a toddler and as a teenager: two looks; a new toddler photo should still match well.
    toddler, teen = unit(a + unit(rng.normal(size=512)) * 0.8), unit(a + unit(rng.normal(size=512)) * 0.8)
    refs = unit(np.vstack([toddler + rng.normal(size=(3, 512)) * 0.01, teen + rng.normal(size=(3, 512)) * 0.01,
                           b + rng.normal(size=(3, 512)) * 0.01]))
    people = np.array([1, 1, 1, 1, 1, 1, 2, 2, 2])
    new = unit(toddler + rng.normal(size=512) * 0.01)[None]
    m = match(new, refs, people)[0]
    assert m.person_id == 1 and m.score > AUTO_ASSIGN  # top-3 nearest, not the average over both looks
    assert match(new, refs, people, [{1}])[0].person_id == 2  # rejected for person 1 -> next best
    assert match(new, refs[:0], people[:0])[0].person_id is None


def test_cluster_groups_people_and_leaves_loners_out():
    rng = np.random.default_rng(0)
    centers = unit(rng.normal(size=(5, 512)))
    emb = unit(np.vstack([centers[i] * 0.78 + unit(rng.normal(size=(30, 512))) * 0.62 for i in range(5)]
                         + [unit(rng.normal(size=(4, 512)))]))  # 4 strangers seen once each
    labels = cluster(emb)
    assert len(set(labels[:150]) - {-1}) == 5
    for i in range(5):
        group = labels[i * 30 : (i + 1) * 30]
        assert np.bincount(group[group >= 0]).max() >= 27  # nearly everyone in one group
    assert (labels[150:] == -1).all()


def test_quality_prefers_big_sharp_frontal():
    front = np.array([[30, 40], [70, 40], [50, 60], [35, 80], [65, 80]], dtype=np.float32)
    profile = front.copy()
    profile[2, 0] = 68  # nose next to one eye: turned away
    assert quality(0.9, 150, 400, front) > quality(0.9, 150, 400, profile)
    assert quality(0.9, 150, 400, front) > quality(0.9, 45, 400, front) > 0
    assert quality(0.9, 150, 400, front) > quality(0.9, 150, 20, front)


def test_faces_stage_runs_on_highlights_only(test_env):
    out = run_all()
    assert out["faces"]["done"] == 3  # IMG_0003 (has a highlight copy), alta IMG_0001, unmatched pano
    # blue IMG_0003: P+Q, white alta: P, teal pano: P+Q
    from sqlalchemy import select

    from photoindex.db import session_scope
    from photoindex.models import Face, Photo

    with session_scope() as s:
        faces = s.scalars(select(Face)).all()
        assert len(faces) == 5
        for f in faces:
            assert 0 <= f.x < 1 and 0 < f.w <= 1 and f.quality > 0
            assert storage.exists(f.crop_key)
        done = s.scalars(select(Photo).where(Photo.face_status == "done")).all()
        assert sorted(p.face_count for p in done) == [1, 2, 2]
        assert {p.face_status for p in s.scalars(select(Photo).where(~Photo.has_highlight, ~Photo.is_highlight_copy))} == {"pending"}
    assert run_all()["faces"] == {}  # nothing new to do


@pytest.fixture
def client(test_env, monkeypatch):
    """Faces for the whole July event too (not just highlights), so there is more to group and match."""
    from photoindex.worker.stages import faces

    monkeypatch.setattr(faces, "SCOPE", "in_processing_set AND NOT ignored")
    run_all()
    from photoindex.api.main import app

    c = TestClient(app)
    tree = {f["name"]: f["id"] for f in c.get("/api/tree").json()}
    july = next(f for f in c.get(f"/api/folders/{tree['2015.album']}").json()["children"]
                if f["name"] == "150704.CO.fourth of july")
    c.put(f"/api/folders/{july['id']}/scope", json={"in_scope": True})
    run_all()
    return c


def settled():
    from photoindex.faces.people import refresher

    assert refresher.wait()


def faces_by_photo(c):
    out = {}
    for p in c.post("/api/search", json={"query": {"collapse_bursts": False}}).json()["photos"]:
        out[p["path"].rsplit("/", 2)[-2] + "/" + p["name"]] = c.get(f"/api/photos/{p['id']}/faces").json()
    return out


def test_name_a_group_then_matches_follow(client):
    c = client
    groups = c.get("/api/clusters").json()
    # July IMG_0001-0004, alta and pano all show P (6); the four colourful ones also show Q; grey IMG_0004 has R
    assert (groups["groups"], groups["ungrouped"]) == (2, 1)
    group = groups["clusters"][0]
    assert group["size"] == 6
    by_photo = faces_by_photo(c)
    pano_p = by_photo["15.highlights/pano.jpg"][0]["id"]
    assert pano_p in [f["id"] for f in c.get(f"/api/clusters/{group['cluster_id']}/faces").json()]

    r = c.post(f"/api/clusters/{group['cluster_id']}/assign", json={"name": "Pat", "exclude_face_ids": [pano_p]})
    assert r.status_code == 200
    pat = r.json()
    settled()
    by_photo = faces_by_photo(c)
    assert by_photo["15.highlights/pano.jpg"][0]["person_id"] is None  # you said it isn't Pat
    july1 = by_photo["150704.CO.fourth of july/IMG_0001.JPG"]
    assert [f["person_name"] for f in july1] == ["Pat", None]  # P named; Q still unknown
    assert pat["photos"] == group["size"] - 1

    # R looks a bit like P: not labelled, but suggested for review
    r_face = by_photo["150704.CO.fourth of july/IMG_0004.JPG"][1]
    assert r_face["person_id"] is None and r_face["suggested_person_id"] == pat["id"]
    assert SUGGEST <= r_face["suggested_score"] < AUTO_ASSIGN
    queue = c.get("/api/review").json()
    assert queue["total"] == 1 and queue["faces"][0]["id"] == r_face["id"]
    assert queue["faces"][0]["examples"] and queue["faces"][0]["suggested_name"] == "Pat"
    assert c.post(f"/api/faces/{r_face['id']}/review", json={"accept": False}).status_code == 200
    settled()
    assert c.get("/api/review").json()["total"] == 0  # rejected stays rejected after re-matching

    # Name one Q; the other three follow automatically
    q_face = july1[1]
    assert c.patch(f"/api/faces/{q_face['id']}", json={"name": "Quinn"}).json()["person_name"] == "Quinn"
    settled()
    people = {p["name"]: p for p in c.get("/api/people").json()}
    assert set(people) == {"Pat", "Quinn"} and people["Quinn"]["photos"] == 4
    assert c.get("/api/clusters").json()["groups"] == 0

    # search by people
    def names(**q):
        return [p["name"] for p in c.post("/api/search", json={"query": q}).json()["photos"]]

    assert len(names(people=[pat["id"]])) == pat["photos"] - 1  # IMG_0002/0003 burst collapses
    both = names(people=[pat["id"], people["Quinn"]["id"]], people_all=True)
    assert both == ["IMG_0001.JPG", "IMG_0002.JPG"]  # pano has Quinn but you said its P isn't Pat
    assert len(names(people=[pat["id"], people["Quinn"]["id"]])) == 5  # either
    assert names(group="solo") == ["IMG_0001.JPG"]  # alta: just Pat
    facets = c.post("/api/search", json={"query": {"people": [people["Quinn"]["id"]]}, "with_facets": True}).json()
    assert {f["label"]: f["count"] for f in facets["facets"]["person"]} == {"Pat": 4, "Quinn": 3}

    # re-running the pipeline keeps your labels
    run_all()
    from photoindex.worker.pipeline import run_stage

    run_stage("people")
    assert {p["name"]: p["photos"] for p in c.get("/api/people").json()} == {
        "Pat": people["Pat"]["photos"], "Quinn": 4}


def test_fix_merge_and_delete_people(client):
    c = client
    group = c.get("/api/clusters").json()["clusters"][0]
    pat = c.post(f"/api/clusters/{group['cluster_id']}/assign", json={"name": "Pat"}).json()
    settled()
    one = c.get(f"/api/people/{pat['id']}/faces").json()["faces"][0]
    assert one["assigned_by"] == "user"

    # "not Pat": unlabelled and never matched back
    assert c.patch(f"/api/faces/{one['id']}", json={"clear": True}).json()["person_id"] is None
    settled()
    assert c.get(f"/api/photos/{one['photo_id']}/faces").json()[0]["person_id"] is None

    # same kid, two names -> merge
    kid = c.post("/api/people", json={"name": "Pat as a baby"}).json()
    c.patch(f"/api/faces/{one['id']}", json={"person_id": kid["id"]})
    merged = c.post(f"/api/people/{kid['id']}/merge", json={"into_id": pat["id"]}).json()
    assert merged["photos"] == group["size"]
    assert [p["name"] for p in c.get("/api/people").json()] == ["Pat"]
    assert c.put(f"/api/people/{pat['id']}", json={"name": "Patricia"}).json()["name"] == "Patricia"

    assert c.delete(f"/api/people/{pat['id']}").status_code == 204
    assert c.get("/api/people").json() == []
    assert c.post("/api/clusters/regroup").status_code == 202
    settled()
    assert c.get("/api/clusters").json()["groups"] == 2  # faces regroup once unnamed


def test_ignore_a_group(client):
    c = client
    group = c.get("/api/clusters").json()["clusters"][0]
    assert c.post(f"/api/clusters/{group['cluster_id']}/ignore", json={}).json()["ignored"] == group["size"]
    assert c.get("/api/clusters").json()["groups"] == 1
    stats = c.get("/api/faces/stats").json()
    assert stats["ignored"] == group["size"]
