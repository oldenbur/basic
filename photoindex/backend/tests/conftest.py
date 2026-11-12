import io
import os
import shutil
from datetime import datetime
from pathlib import Path

import psycopg
import pytest
from PIL import Image

ADMIN_URL = os.environ.get("TEST_ADMIN_DSN", "postgresql://photoindex:photoindex@localhost:5432/photoindex")
TEST_DB = "photoindex_test"


def make_jpeg(path: Path, taken: datetime | None, color=(200, 80, 40), model="X100V", gps=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (1200, 800), color)
    # Vary pixels a little so phashes differ between photos.
    for x in range(0, 1200, 97):
        im.paste((color[2], color[0], color[1]), (x, (x * 7) % 700, x + 40, (x * 7) % 700 + 60))
    exif = Image.Exif()
    exif[0x010F] = "FUJIFILM"
    exif[0x0110] = model
    if taken:
        ifd = exif.get_ifd(0x8769)
        ifd[0x9003] = taken.strftime("%Y:%m:%d %H:%M:%S")
    if gps:
        lat, lon = gps
        g = exif.get_ifd(0x8825)
        g[1], g[2] = ("N" if lat >= 0 else "S"), (abs(int(lat)), 0, 0)
        g[3], g[4] = ("E" if lon >= 0 else "W"), (abs(int(lon)), 0, 0)
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif, quality=80)
    path.write_bytes(buf.getvalue())


def build_library(root: Path) -> Path:
    """A tiny library exercising every linking/parsing path. Also used to seed a dev database."""
    july = root / "2015" / "150704.CO.fourth of july"
    make_jpeg(july / "IMG_0001.JPG", datetime(2015, 7, 4, 10, 0, 0), gps=(39.5, -105.5))
    make_jpeg(july / "IMG_0002.JPG", datetime(2015, 7, 4, 10, 5, 0), (10, 200, 10))
    make_jpeg(july / "IMG_0003.JPG", datetime(2015, 7, 4, 10, 5, 1), (10, 10, 200))  # burst with 0002
    make_jpeg(july / "IMG_0004.JPG", datetime(2015, 7, 9, 9, 0, 0), (90, 90, 90))  # 5 days off the event date
    alta = root / "2015" / "150801.ut.alta"
    make_jpeg(alta / "IMG_0001.JPG", datetime(2015, 8, 1, 8, 0, 0), (250, 250, 250))  # counter collision

    hl = root / "2015" / "Highlights"
    hl.mkdir(parents=True, exist_ok=True)
    shutil.copy(july / "IMG_0003.JPG", hl / "IMG_0003.JPG")
    # Re-exported copy of the *alta* IMG_0001: different bytes, same EXIF time.
    make_jpeg(hl / "IMG_0001-edited.jpg", datetime(2015, 8, 1, 8, 0, 0), (240, 240, 240))
    make_jpeg(hl / "pano.jpg", datetime(2015, 7, 20, 12, 0, 0), (0, 120, 120))  # no original anywhere

    make_jpeg(root / "2016" / "160101_CA_new year" / "IMG_9000.JPG", datetime(2016, 1, 1, 0, 1, 0))
    make_jpeg(root / "Old Scans" / "scan1.jpg", None, (120, 60, 0))
    (root / "2016" / "notes.txt").write_text("not a photo")
    return root


@pytest.fixture
def library(tmp_path: Path) -> Path:
    return build_library(tmp_path / "lib")


@pytest.fixture
def test_env(monkeypatch, library):
    """Point the app at a fresh test database, a test bucket, and the local fixture library."""
    try:
        with psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
            conn.execute(f"CREATE DATABASE {TEST_DB}")
    except psycopg.OperationalError:
        pytest.skip("Postgres not running (docker compose -f deploy/docker-compose.dev.yml up -d)")

    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://photoindex:photoindex@localhost:5432/{TEST_DB}")
    monkeypatch.setenv("SOURCE", "local")
    monkeypatch.setenv("PHOTO_ROOT", str(library))
    monkeypatch.setenv("S3_BUCKET", "photoindex-test")
    monkeypatch.setenv("WORKERS", "2")

    from photoindex import config, db, storage

    for cached in (config.get_settings, db.get_engine, storage._client):
        cached.cache_clear()

    from photoindex.models import Base

    Base.metadata.create_all(db.get_engine())
    yield library
    db.get_engine().dispose()
    for cached in (config.get_settings, db.get_engine, storage._client):
        cached.cache_clear()
