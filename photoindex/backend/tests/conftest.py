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
    july = root / "2015.album" / "150704.CO.fourth of july"
    make_jpeg(july / "IMG_0001.JPG", datetime(2015, 7, 4, 10, 0, 0), gps=(39.5, -105.5))
    make_jpeg(july / "IMG_0002.JPG", datetime(2015, 7, 4, 10, 5, 0), (10, 200, 10))
    make_jpeg(july / "IMG_0003.JPG", datetime(2015, 7, 4, 10, 5, 1), (10, 10, 200))  # burst with 0002
    make_jpeg(july / "IMG_0004.JPG", datetime(2015, 9, 9, 9, 0, 0), (90, 90, 90))  # 67 days off the event date
    alta = root / "2015.album" / "150801.ut.alta"
    make_jpeg(alta / "IMG_0001.JPG", datetime(2015, 8, 1, 8, 0, 0), (250, 250, 250))  # counter collision

    hl = root / "2015.album" / "15.highlights"
    hl.mkdir(parents=True, exist_ok=True)
    shutil.copy(july / "IMG_0003.JPG", hl / "IMG_0003.JPG")
    # Re-exported copy of the *alta* IMG_0001: different bytes, same EXIF time.
    make_jpeg(hl / "IMG_0001-edited.jpg", datetime(2015, 8, 1, 8, 0, 0), (240, 240, 240))
    make_jpeg(hl / "pano.jpg", datetime(2015, 7, 20, 12, 0, 0), (0, 120, 120))  # no original anywhere
    # A conflicted copy of the July event: ignored, so the highlight never links into it.
    conflict = root / "2015.album" / "150704.CO.fourth of july (Paul's conflicted copy 2026-01-30)"
    conflict.mkdir(parents=True, exist_ok=True)
    shutil.copy(july / "IMG_0003.JPG", conflict / "IMG_0003.JPG")

    make_jpeg(root / "2016.album" / "160320.Oslo" / "IMG_8000.JPG", datetime(2016, 3, 20, 12, 0, 0))  # abroad
    make_jpeg(root / "2016.album" / "160101_CA_new year" / "IMG_9000.JPG", datetime(2016, 1, 1, 0, 1, 0))
    make_jpeg(root / "2014" / "IMG_7000.JPG", datetime(2014, 1, 1, 0, 1, 0))  # year without .album
    make_jpeg(root / "Old Scans" / "scan1.jpg", None, (120, 60, 0))
    (root / "2016.album" / "notes.txt").write_text("not a photo")
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

    with db.get_engine().begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(db.get_engine())
    yield library
    db.get_engine().dispose()
    for cached in (config.get_settings, db.get_engine, storage._client):
        cached.cache_clear()


class FakeFaceEngine:
    """Stands in for the face models (the fixture photos are flat colours, not faces). Every photo shows
    person P; colourful photos also show Q; grey ones also show R, who looks a bit like P (a review-queue case)."""

    def __init__(self):
        import numpy as np

        rng = np.random.default_rng(1)
        self.base = {k: v / np.linalg.norm(v) for k, v in zip("PQX", rng.normal(size=(3, 512)))}

    def _vec(self, who: str, seed: int):
        import numpy as np

        if who == "R":  # ~0.48 similar to P: worth asking about, too loose to join P's group
            v = self.base["P"] * 0.48 + self.base["X"] * 0.877
        else:
            v = self.base[who] + np.random.default_rng(seed).normal(size=512) * 0.005
        return v / np.linalg.norm(v)

    def detect(self, rgb, min_score=0.5):
        import numpy as np

        from photoindex.faces.engine import DetectedFace

        r, g, b = (int(c) for c in rgb[-3, -3])  # a corner clear of make_jpeg's pattern: the base colour
        seed = r * 65536 + g * 256 + b
        h, w = rgb.shape[:2]
        colourful = max(r, g, b) - min(r, g, b) > 50
        who = ["P"] + (["Q"] if colourful else []) + (["R"] if not colourful and max(r, g, b) < 128 else [])
        lm = np.array([[30, 40], [70, 40], [50, 60], [35, 80], [65, 80]], dtype=np.float32)
        return [DetectedFace(box=(w * 0.1 + i * w * 0.3, h * 0.1, w * 0.2, h * 0.2), score=0.9, landmarks=lm,
                             embedding=self._vec(name, seed + i), sharpness=400.0)
                for i, name in enumerate(who)]


@pytest.fixture(autouse=True)
def fake_face_engine(monkeypatch):
    from photoindex.faces import engine

    fake = FakeFaceEngine()
    monkeypatch.setattr(engine, "get_engine", lambda: fake)
    return fake


class FakeBatches:
    """Stands in for client.messages.batches. Answers depend on the photo's colour (read from the image sent),
    the model, and the context text, so tests can check what was sent and how answers are applied."""

    def __init__(self):
        self.batches: dict[str, list[dict]] = {}
        self.hold = False  # True: batches stay "in_progress"
        self.fail_once: set[int] = set()  # photo ids that get a retryable error the first time
        self.invalid: set[int] = set()  # photo ids that get a non-retryable error
        self.refuse: set[int] = set()

    def create(self, requests):
        from types import SimpleNamespace

        bid = f"msgbatch_{len(self.batches) + 1}"
        self.batches[bid] = list(requests)
        return SimpleNamespace(id=bid, processing_status="in_progress")

    def retrieve(self, batch_id):
        from types import SimpleNamespace

        return SimpleNamespace(id=batch_id, processing_status="in_progress" if self.hold else "ended")

    @staticmethod
    def colour(params) -> tuple[int, int, int]:
        import base64

        img = next(c for c in params["messages"][0]["content"] if c["type"] == "image")
        with Image.open(io.BytesIO(base64.b64decode(img["source"]["data"]))) as im:
            return im.convert("RGB").getpixel((im.width - 3, im.height - 3))

    def answer(self, params) -> dict:
        r, g, b = self.colour(params)
        ctx = params["messages"][0]["content"][1]["text"]
        colourful = max(r, g, b) - min(r, g, b) > 50
        haiku = params["model"] == "claude-haiku-5-5"
        abroad = "outside the US" in ctx
        return {
            "rotation": 90 if (r, g, b) != (0, 0, 0) and abs(r - 0) < 12 and abs(g - 120) < 12 and abs(b - 120) < 12 else 0,
            "caption": ("Kids skiing" if colourful else "A hike by a lake") + (" (haiku)" if haiku else ""),
            "scene": "Ski Slopes" if colourful else "alpine lake",
            "setting": "outdoor",
            "activities": ["Downhill Skiing"] if colourful else ["hiking"],
            "objects": ["Sleds", "fire"] if colourful else ["waterfalls"],
            "animals": ["Dogs"] if colourful and not haiku else [],
            "camping_gear": ["Tents"] if not colourful else [],
            "vehicles": [{"type": "Pickup", "make_model": "Jeep Wrangler", "color": "red"}] if colourful else [],
            "landmarks": ["Eldora"] if colourful else [],
            "location": ({"country": "Norway", "region": "Oslo", "city": "Oslo", "place_name": "Vigeland Park",
                          "confidence": "medium"} if abroad else
                         {"country": "United States", "region": "Colorado", "city": "Nederland", "place_name": "",
                          "confidence": "low"}),
            "people_count": 2,
            "aesthetic": 9 if colourful else 4,
            "confidence": "high",
        }

    def results(self, batch_id):
        import json
        from types import SimpleNamespace as NS

        for req in self.batches[batch_id]:
            pid = int(req["custom_id"][1:])
            if pid in self.invalid:
                yield NS(custom_id=req["custom_id"], result=NS(type="errored", error=NS(
                    type="error", error=NS(type="invalid_request_error", message="bad image"))))
                continue
            if pid in self.fail_once:
                self.fail_once.discard(pid)
                yield NS(custom_id=req["custom_id"], result=NS(type="errored", error=NS(
                    type="error", error=NS(type="api_error", message="overloaded"))))
                continue
            refused = pid in self.refuse
            msg = NS(stop_reason="refusal" if refused else "end_turn",
                     content=[NS(type="text", text="" if refused else json.dumps(self.answer(req["params"])))],
                     usage=NS(input_tokens=1200, output_tokens=300, cache_read_input_tokens=1500,
                              cache_creation_input_tokens=0))
            yield NS(custom_id=req["custom_id"], result=NS(type="succeeded", message=msg))


@pytest.fixture(autouse=True)
def fake_anthropic(monkeypatch):
    from types import SimpleNamespace

    from photoindex.tagging import client

    batches = FakeBatches()
    fake = SimpleNamespace(messages=SimpleNamespace(batches=batches))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(client, "get_client", lambda: fake)
    return batches
