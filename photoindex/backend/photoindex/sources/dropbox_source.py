import base64
from collections.abc import Iterator

import dropbox
from dropbox import files

from photoindex.sources import DeletedEntry, Entry, FileEntry, FolderEntry

THUMB_BATCH = 25  # Dropbox limit for get_thumbnail_batch


class DropboxSource:
    def __init__(self, app_key: str, app_secret: str, refresh_token: str, root: str):
        self.root = root.rstrip("/").lower()
        if not refresh_token:
            raise RuntimeError("DROPBOX_REFRESH_TOKEN is not set; run `photoindex dropbox-auth` first")
        self.dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret,
            max_retries_on_rate_limit=10,
            max_retries_on_error=5,
            timeout=120,
        )

    def list_changes(self, cursor: str | None) -> Iterator[tuple[list[Entry], str]]:
        if cursor:
            res = self.dbx.files_list_folder_continue(cursor)
        else:
            res = self.dbx.files_list_folder(self.root, recursive=True, limit=2000)
        while True:
            yield [e for e in map(_convert, res.entries) if e is not None], res.cursor
            if not res.has_more:
                return
            res = self.dbx.files_list_folder_continue(res.cursor)

    def read_head(self, path: str, nbytes: int) -> bytes:
        _, resp = self.dbx.files_download(path)
        try:
            buf = bytearray()
            for chunk in resp.iter_content(chunk_size=32 * 1024):
                buf.extend(chunk)
                if len(buf) >= nbytes:
                    break
            return bytes(buf[:nbytes])
        finally:
            resp.close()

    def thumbnails(self, paths: list[str], size: str) -> dict[str, bytes | None]:
        out: dict[str, bytes | None] = {}
        for i in range(0, len(paths), THUMB_BATCH):
            chunk = paths[i : i + THUMB_BATCH]
            args = [
                files.ThumbnailArg(
                    path=p,
                    format=files.ThumbnailFormat.jpeg,
                    size=getattr(files.ThumbnailSize, size),
                    mode=files.ThumbnailMode.bestfit,
                )
                for p in chunk
            ]
            res = self.dbx.files_get_thumbnail_batch(args)
            for p, entry in zip(chunk, res.entries, strict=True):
                out[p] = base64.b64decode(entry.get_success().thumbnail) if entry.is_success() else None
        return out

    def temporary_link(self, path: str) -> str:
        return self.dbx.files_get_temporary_link(path).link


def _convert(e) -> Entry | None:
    if isinstance(e, files.FileMetadata):
        return FileEntry(e.id, e.path_lower, e.path_display, e.size, e.content_hash, e.client_modified)
    if isinstance(e, files.FolderMetadata):
        return FolderEntry(e.id, e.path_lower, e.path_display)
    if isinstance(e, files.DeletedMetadata):
        return DeletedEntry(e.path_lower)
    return None


def run_auth_flow(app_key: str, app_secret: str) -> str:
    """Interactive one-time OAuth flow; returns a long-lived refresh token."""
    flow = dropbox.DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type="offline")
    print("1. Open:", flow.start())
    print("2. Click Allow, then copy the authorization code.")
    code = input("3. Paste the code here: ").strip()
    return flow.finish(code).refresh_token
