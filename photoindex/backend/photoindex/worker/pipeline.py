import logging
import time

from photoindex.config import get_settings
from photoindex.db import session_scope
from photoindex.sources import PhotoSource, get_source
from photoindex.worker.stages import faces, link, meta, parse, places, sync, thumbs

log = logging.getLogger(__name__)

STAGES = ("sync", "parse", "link", "meta", "places", "thumbs", "faces", "people", "tag", "album_faces", "album_events", "album_place")


def run_stage(name: str, source: PhotoSource | None = None) -> dict:
    s = get_settings()
    source = source or get_source()
    with session_scope() as session:
        match name:
            case "sync":
                stats = sync.run(session, source)
            case "parse":
                stats = parse.run(session, source.root, s.album_folder_list)
            case "link":
                stats = link.run(session)
            case "meta":
                stats = meta.run(session, source, s.exif_head_bytes, s.workers)
            case "places":
                stats = places.run(session)
            case "thumbs":
                stats = thumbs.run(session, source, s.workers)
            case "faces":
                stats = faces.run(session, source, s.workers)
            case "people":  # re-match and regroup faces without detecting anything new
                from photoindex.faces.people import refresh

                return refresh(session)
            case "album_faces":  # faces in the scanned album prints, matched to the people you've named
                from photoindex.albums import faces as album_faces

                stats = album_faces.run(session, source, s.workers)
            case "album_events":  # split the albums into events
                from photoindex.albums import events as album_events

                stats = album_events.run(session, s.album_me)
            case "album_place":  # settle a month and a year folder for every dated album print
                from photoindex.albums import placement

                stats = placement.run(session, s.album_me)
            case "tag":  # collect finished AI batches and send more (the API server also does this every minute)
                from photoindex.tagging.batches import tick

                return tick(session, source)
            case _:
                raise ValueError(f"unknown stage {name!r}")
    log.info("%s: %s", name, dict(stats))
    return dict(stats)


def run_all(source: PhotoSource | None = None) -> dict:
    source = source or get_source()
    out = {}
    for name in ("sync", "parse", "link", "meta"):
        out[name] = run_stage(name, source)
    # Ambiguous highlight matches need EXIF from the meta stage; link again to settle them,
    # then pick up EXIF for any highlights that just became standalone.
    out["link2"] = run_stage("link", source)
    out["meta2"] = run_stage("meta", source)
    out["places"] = run_stage("places", source)
    out["thumbs"] = run_stage("thumbs", source)
    out["faces"] = run_stage("faces", source)
    out["tag"] = run_stage("tag", source)
    return out


def loop(interval: int) -> None:
    source = get_source()
    while True:
        try:
            run_all(source)
        except Exception:
            log.exception("pipeline run failed; retrying after %ss", interval)
        time.sleep(interval)
