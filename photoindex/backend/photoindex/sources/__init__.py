"""Photo sources: where the library lives. Dropbox in production, a local directory in dev/tests."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp", ".gif", ".bmp"})


@dataclass
class FolderEntry:
    id: str
    path_lower: str
    path_display: str


@dataclass
class FileEntry:
    id: str
    path_lower: str
    path_display: str
    size: int
    content_hash: str | None
    client_modified: datetime | None


@dataclass
class DeletedEntry:
    path_lower: str


Entry = FolderEntry | FileEntry | DeletedEntry


class PhotoSource(Protocol):
    root: str  # path prefix (lowercase, no trailing slash) of the library within the source; "" = whole source

    def list_changes(self, cursor: str | None) -> Iterator[tuple[list[Entry], str]]:
        """Yield (entries, cursor) pages. With cursor=None, lists everything under self.root recursively."""
        ...

    def read_head(self, path: str, nbytes: int) -> bytes:
        """Return the first nbytes of a file (enough for EXIF)."""
        ...

    def thumbnails(self, paths: list[str], size: str) -> dict[str, bytes | None]:
        """JPEG thumbnails keyed by path. size is a Dropbox size name, e.g. 'w640h480'. None on failure."""
        ...

    def temporary_link(self, path: str) -> str:
        ...


def is_image(path: str) -> bool:
    dot = path.rfind(".")
    return dot >= 0 and path[dot:].lower() in IMAGE_EXTS


def get_source() -> PhotoSource:
    from photoindex.config import get_settings

    s = get_settings()
    if s.source == "local":
        from photoindex.sources.local import LocalSource

        return LocalSource(s.photo_root)
    from photoindex.sources.dropbox_source import DropboxSource

    return DropboxSource(s.dropbox_app_key, s.dropbox_app_secret, s.dropbox_refresh_token, s.photo_root)
