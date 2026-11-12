"""A PhotoSource backed by a local directory, mirroring Dropbox semantics (lowercase paths, content hash)."""

import hashlib
import io
import json
import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from photoindex.sources import DeletedEntry, Entry, FileEntry, FolderEntry

DROPBOX_SIZES = {
    "w256h256": (256, 256), "w480h320": (480, 320), "w640h480": (640, 480),
    "w960h640": (960, 640), "w1024h768": (1024, 768), "w2048h1536": (2048, 1536),
}


def dropbox_content_hash(path: Path) -> str:
    """Dropbox's content_hash: sha256 over the concatenated sha256 digests of each 4 MiB block."""
    outer = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            outer.update(hashlib.sha256(block).digest())
    return outer.hexdigest()


class LocalSource:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir).resolve()
        self.root = ""

    def _abs(self, path: str) -> Path:
        # Dropbox-style paths are case-insensitive; resolve against the real on-disk names.
        rel = path.lstrip("/")
        p = self.base
        for part in Path(rel).parts:
            match = next((c for c in p.iterdir() if c.name.lower() == part.lower()), None)
            if match is None:
                raise FileNotFoundError(path)
            p = match
        return p

    def _snapshot(self) -> dict[str, Entry]:
        snap: dict[str, Entry] = {}
        for dirpath, dirnames, filenames in os.walk(self.base):
            dirnames.sort()
            for name in dirnames + sorted(filenames):
                p = Path(dirpath, name)
                display = "/" + p.relative_to(self.base).as_posix()
                ident = f"id:{p.stat().st_ino}"
                if p.is_dir():
                    snap[display.lower()] = FolderEntry(ident, display.lower(), display)
                elif not name.startswith("."):
                    st = p.stat()
                    snap[display.lower()] = FileEntry(
                        ident, display.lower(), display, st.st_size, dropbox_content_hash(p),
                        datetime.fromtimestamp(st.st_mtime),
                    )
        return snap

    def list_changes(self, cursor: str | None) -> Iterator[tuple[list[Entry], str]]:
        # The cursor is the set of paths seen last time, so deletions can be reported like Dropbox does.
        prev = set(json.loads(cursor)) if cursor else set()
        snap = self._snapshot()
        entries: list[Entry] = [DeletedEntry(p) for p in sorted(prev - snap.keys())]
        entries += list(snap.values())
        yield entries, json.dumps(sorted(snap))

    def read_head(self, path: str, nbytes: int) -> bytes:
        with self._abs(path).open("rb") as f:
            return f.read(nbytes)

    def thumbnails(self, paths: list[str], size: str) -> dict[str, bytes | None]:
        box = DROPBOX_SIZES[size]
        out: dict[str, bytes | None] = {}
        for p in paths:
            try:
                with Image.open(self._abs(p)) as im:
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    im.thumbnail(box)
                    buf = io.BytesIO()
                    im.save(buf, "JPEG", quality=85)
                    out[p] = buf.getvalue()
            except Exception:
                out[p] = None
        return out

    def temporary_link(self, path: str) -> str:
        return self._abs(path).as_uri()
