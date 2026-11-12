"""End-to-end: local fixture library -> Postgres + S3, then the API on top. Needs the dev compose infra."""

import shutil

from fastapi.testclient import TestClient
from sqlalchemy import select

from photoindex import storage
from photoindex.db import session_scope
from photoindex.models import Folder, Photo
from photoindex.worker.pipeline import run_all


def photos_by_path() -> dict[str, Photo]:
    with session_scope() as s:
        return {p.path_lower: p for p in s.scalars(select(Photo))}


def folders_by_name() -> dict[str, Folder]:
    with session_scope() as s:
        return {f.name: f for f in s.scalars(select(Folder))}


def test_full_pipeline(test_env):
    run_all()
    photos = photos_by_path()
    folders = folders_by_name()

    # sync: only images, folders linked to parents
    assert len(photos) == 10
    assert not any(p.endswith(".txt") for p in photos)
    assert folders["150704.CO.fourth of july"].parent_id == folders["2015"].id

    # parse
    assert folders["2015"].kind == "year"
    assert folders["Highlights"].kind == "highlights"
    july = folders["150704.CO.fourth of july"]
    assert (july.kind, july.state, july.parse_ok, july.issues) == ("event", "CO", True, None)
    assert folders["150801.ut.alta"].suggested_name == "150801.UT.alta"
    ny = folders["160101_CA_new year"]
    assert not ny.parse_ok and ny.suggested_name == "160101.CA.new year"
    assert {i["code"] for i in folders["Old Scans"].issues} == {"unrecognized"}

    # link: exact copy by hash, re-export settled by EXIF time, pano stands alone
    hl3 = photos["/2015/highlights/img_0003.jpg"]
    hl1 = photos["/2015/highlights/img_0001-edited.jpg"]
    pano = photos["/2015/highlights/pano.jpg"]
    orig3 = photos["/2015/150704.co.fourth of july/img_0003.jpg"]
    alta1 = photos["/2015/150801.ut.alta/img_0001.jpg"]
    assert (hl3.link_method, hl3.original_id) == ("hash", orig3.id)
    assert (hl1.link_method, hl1.original_id) == ("stem_time", alta1.id)
    assert (pano.link_method, pano.original_id) == ("none", None)

    # processing set = linked originals + standalone highlight; copies never processed twice
    processing = {p.path_lower for p in photos.values() if p.in_processing_set}
    assert processing == {orig3.path_lower, alta1.path_lower, pano.path_lower}

    # meta
    assert orig3.taken_at.isoformat() == "2015-07-04T10:05:01"
    assert orig3.camera_model == "X100V"
    assert photos["/2015/150704.co.fourth of july/img_0002.jpg"].meta_status == "pending"  # not in set
    # ...but the ambiguous-match candidate had its EXIF read to settle the link
    assert photos["/2015/150704.co.fourth of july/img_0001.jpg"].meta_status == "done"

    # thumbs in S3, phash computed, nothing else thumbnailed
    for p in (orig3, alta1, pano):
        assert p.thumb_status == "done" and len(p.phash) == 16
        assert storage.exists(p.thumb_key)
    assert all(p.thumb_status == "pending" for p in photos.values() if not p.in_processing_set)


def test_scope_bursts_and_mismatch(test_env):
    run_all()
    from photoindex.api.main import app

    client = TestClient(app)
    july_id = folders_by_name()["150704.CO.fourth of july"].id
    r = client.put(f"/api/folders/{july_id}/scope", json={"in_scope": True})
    assert r.status_code == 200 and r.json()["counts"]["processing"] == 4
    run_all()

    photos = photos_by_path()
    b2 = photos["/2015/150704.co.fourth of july/img_0002.jpg"]
    b3 = photos["/2015/150704.co.fourth of july/img_0003.jpg"]
    assert b2.burst_group_id is not None and b2.burst_group_id == b3.burst_group_id
    assert photos["/2015/150704.co.fourth of july/img_0001.jpg"].burst_group_id is None
    assert photos["/2015/150704.co.fourth of july/img_0004.jpg"].date_mismatch_days == 5
    gps = photos["/2015/150704.co.fourth of july/img_0001.jpg"]
    assert (gps.lat, gps.lon) == (39.0, -105.0)


def test_incremental_sync_handles_deletes(test_env):
    run_all()
    shutil.rmtree(test_env / "Old Scans")
    (test_env / "2015" / "Highlights" / "pano.jpg").unlink()
    run_all()
    photos = photos_by_path()
    assert photos["/old scans/scan1.jpg"].deleted
    assert photos["/2015/highlights/pano.jpg"].deleted
    assert not photos["/2015/highlights/pano.jpg"].in_processing_set
    assert folders_by_name()["Old Scans"].deleted


def test_api(test_env):
    run_all()
    from photoindex.api.main import app

    client = TestClient(app)
    tree = {f["name"]: f for f in client.get("/api/tree").json()}
    assert set(tree) == {"2015", "2016", "Old Scans"}
    assert tree["2015"]["counts"] == {"photos": 8, "processing": 3, "thumbs": 3, "highlights": 3, "issues": 1}

    detail = client.get(f"/api/folders/{tree['2015']['id']}").json()
    assert [c["name"] for c in detail["children"]] == ["150704.CO.fourth of july", "150801.ut.alta", "Highlights"]
    assert detail["breadcrumbs"] == [{"id": tree["2015"]["id"], "name": "2015"}]

    hl = next(c for c in detail["children"] if c["kind"] == "highlights")
    page = client.get(f"/api/folders/{hl['id']}/photos").json()
    # copies sort and display using their original's EXIF and thumbnail
    assert [p["name"] for p in page["photos"]] == ["IMG_0003.JPG", "pano.jpg", "IMG_0001-edited.jpg"]
    assert all(p["thumb_url"] for p in page["photos"])
    assert page["photos"][0]["taken_at"] == "2015-07-04T10:05:01"

    issues = client.get("/api/issues", params={"severity": "error"}).json()
    assert {f["name"] for f in issues} == {"160101_CA_new year", "Old Scans"}

    stats = client.get("/api/stats").json()
    assert stats["highlights_linked"] == 2 and stats["highlights_unmatched"] == 1
    assert stats["processing_set"] == 3 and stats["thumbs_done"] == 3
