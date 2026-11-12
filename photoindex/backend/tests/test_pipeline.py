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
    assert len(photos) == 13
    assert not any(p.endswith(".txt") for p in photos)
    assert folders["150704.CO.fourth of july"].parent_id == folders["2015.album"].id

    # parse
    assert folders["2015.album"].kind == "year"
    assert folders["15.highlights"].kind == "highlights"
    july = folders["150704.CO.fourth of july"]
    assert (july.kind, july.state, july.parse_ok, july.issues) == ("event", "CO", True, None)
    assert folders["150801.ut.alta"].suggested_name == "150801.UT.alta"
    oslo = folders["160320.Oslo"]
    assert (oslo.kind, oslo.state, oslo.event_name) == ("event", None, "Oslo")
    ny = folders["160101_CA_new year"]
    assert (ny.kind, ny.parse_ok, ny.suggested_name) == ("ignored", False, "160101.CA.new year")
    for name in ("Old Scans", "2014"):
        assert {i["code"] for i in folders[name].issues} == {"ignored"}
    ignored = {p for p, ph in photos.items() if ph.ignored}
    assert ignored == {"/2016.album/160101_ca_new year/img_9000.jpg", "/2014/img_7000.jpg", "/old scans/scan1.jpg",
                       "/2015.album/150704.co.fourth of july (paul's conflicted copy 2026-01-30)/img_0003.jpg"}

    # link: exact copy by hash, re-export settled by EXIF time, pano stands alone
    hl3 = photos["/2015.album/15.highlights/img_0003.jpg"]
    hl1 = photos["/2015.album/15.highlights/img_0001-edited.jpg"]
    pano = photos["/2015.album/15.highlights/pano.jpg"]
    orig3 = photos["/2015.album/150704.co.fourth of july/img_0003.jpg"]
    alta1 = photos["/2015.album/150801.ut.alta/img_0001.jpg"]
    assert (hl3.link_method, hl3.original_id) == ("hash", orig3.id)
    assert (hl1.link_method, hl1.original_id) == ("stem_time", alta1.id)
    assert (pano.link_method, pano.original_id) == ("none", None)

    # processing set = linked originals + standalone highlight; copies never processed twice
    processing = {p.path_lower for p in photos.values() if p.in_processing_set}
    assert processing == {orig3.path_lower, alta1.path_lower, pano.path_lower}

    # meta
    assert orig3.taken_at.isoformat() == "2015-07-04T10:05:01"
    assert orig3.camera_model == "X100V"
    assert photos["/2015.album/150704.co.fourth of july/img_0002.jpg"].meta_status == "pending"  # not in set
    # ...but the ambiguous-match candidate had its EXIF read to settle the link
    assert photos["/2015.album/150704.co.fourth of july/img_0001.jpg"].meta_status == "done"

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
    b2 = photos["/2015.album/150704.co.fourth of july/img_0002.jpg"]
    b3 = photos["/2015.album/150704.co.fourth of july/img_0003.jpg"]
    assert b2.burst_group_id is not None and b2.burst_group_id == b3.burst_group_id
    assert photos["/2015.album/150704.co.fourth of july/img_0001.jpg"].burst_group_id is None
    assert photos["/2015.album/150704.co.fourth of july/img_0004.jpg"].date_mismatch_days == 67
    gps = photos["/2015.album/150704.co.fourth of july/img_0001.jpg"]
    assert (gps.lat, gps.lon) == (39.0, -105.0)


def test_incremental_sync_handles_deletes(test_env):
    run_all()
    shutil.rmtree(test_env / "Old Scans")
    (test_env / "2015.album" / "15.highlights" / "pano.jpg").unlink()
    run_all()
    photos = photos_by_path()
    assert photos["/old scans/scan1.jpg"].deleted
    assert photos["/2015.album/15.highlights/pano.jpg"].deleted
    assert not photos["/2015.album/15.highlights/pano.jpg"].in_processing_set
    assert folders_by_name()["Old Scans"].deleted


def test_api(test_env):
    run_all()
    from photoindex.api.main import app

    client = TestClient(app)
    tree = {f["name"]: f for f in client.get("/api/tree").json()}
    assert set(tree) == {"2015.album", "2016.album"}  # ignored folders aren't browsable
    assert tree["2015.album"]["counts"] == {
        "photos": 8, "processing": 3, "thumbs": 3, "highlights": 3, "linked": 2, "ignored": 1, "issues": 1}

    detail = client.get(f"/api/folders/{tree['2015.album']['id']}").json()
    assert [c["name"] for c in detail["children"]] == ["150704.CO.fourth of july", "150801.ut.alta", "15.highlights"]
    assert detail["breadcrumbs"] == [{"id": tree["2015.album"]["id"], "name": "2015.album"}]
    oslo = client.get(f"/api/folders/{tree['2016.album']['id']}").json()["children"]
    assert [(c["name"], c["abroad"]) for c in oslo] == [("160320.Oslo", True)]

    hl = next(c for c in detail["children"] if c["kind"] == "highlights")
    page = client.get(f"/api/folders/{hl['id']}/photos").json()
    # copies sort and display using their original's EXIF and thumbnail
    assert [p["name"] for p in page["photos"]] == ["IMG_0003.JPG", "pano.jpg", "IMG_0001-edited.jpg"]
    assert all(p["thumb_url"] for p in page["photos"])
    assert page["photos"][0]["taken_at"] == "2015-07-04T10:05:01"

    ignored = client.get("/api/issues", params={"severity": "ignored"}).json()
    assert {f["name"] for f in ignored} == {
        "160101_CA_new year", "Old Scans", "2014", "150704.CO.fourth of july (Paul's conflicted copy 2026-01-30)"}
    assert {f["name"] for f in client.get("/api/issues", params={"severity": "warning"}).json()} == {"150801.ut.alta"}

    stats = client.get("/api/stats").json()
    assert stats["highlights_linked"] == 2 and stats["highlights_unmatched"] == 1
    assert stats["processing_set"] == 3 and stats["thumbs_done"] == 3
    assert (stats["photos"], stats["photos_ignored"], stats["folders_ignored"]) == (9, 4, 4)
