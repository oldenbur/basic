import logging
import time

from photoindex.config import get_settings
from photoindex.db import session_scope
from photoindex.sources import PhotoSource, get_source
from photoindex.worker.stages import link, meta, parse, sync, thumbs

log = logging.getLogger(__name__)

STAGES = ("sync", "parse", "link", "meta", "thumbs")


def run_stage(name: str, source: PhotoSource | None = None) -> dict:
    s = get_settings()
    source = source or get_source()
    with session_scope() as session:
        match name:
            case "sync":
                stats = sync.run(session, source)
            case "parse":
                stats = parse.run(session, source.root)
            case "link":
                stats = link.run(session)
            case "meta":
                stats = meta.run(session, source, s.exif_head_bytes, s.workers)
            case "thumbs":
                stats = thumbs.run(session, source, s.workers)
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
    out["thumbs"] = run_stage("thumbs", source)
    return out


def loop(interval: int) -> None:
    source = get_source()
    while True:
        try:
            run_all(source)
        except Exception:
            log.exception("pipeline run failed; retrying after %ss", interval)
        time.sleep(interval)
