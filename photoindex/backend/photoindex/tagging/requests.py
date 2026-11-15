"""Build one Messages API request per photo: the frozen system prompt (cached), the photo at 1024px, and what the
library already knows about it (event folder, date, place, recognised people)."""

import base64
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from photoindex import display, storage
from photoindex.config import get_settings
from photoindex.models import Face, Folder, Person, Photo
from photoindex.sources import PhotoSource
from photoindex.tagging.pricing import MODELS
from photoindex.tagging.prompt import SCHEMA, SYSTEM

log = logging.getLogger(__name__)
IMAGE_PX = 1024  # long side; ~1,000 image tokens, plenty to recognise skis or a Jeep
MAX_TOKENS = 4000  # the answer is ~300 tokens; the rest is headroom for Opus's (low-effort) thinking


@dataclass
class Prepared:
    photo_id: int
    rotation: int  # the photo's rotation when the image was made (the model's answer is relative to it)
    image: bytes
    context: str


def _image(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((IMAGE_PX, IMAGE_PX))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        return buf.getvalue()


def _root_relative(path: str) -> str:
    root = get_settings().photo_root.rstrip("/")
    return path[len(root) + 1:] if path.lower().startswith(root.lower() + "/") else path


def contexts(session: Session, ids: list[int]) -> dict[int, str]:
    ev = aliased(Folder)
    rows = session.execute(
        select(Photo, Folder, ev).outerjoin(Folder, Folder.id == Photo.folder_id)
        .outerjoin(ev, ev.id == Folder.event_folder_id).where(Photo.id.in_(ids))
    ).all()
    names: dict[int, list[str]] = {}
    for pid, name in session.execute(
        select(Face.photo_id, Person.name).join(Person, Person.id == Face.person_id)
        .where(Face.photo_id.in_(ids), ~Face.ignored).order_by(Face.photo_id, Face.x)
    ):
        names.setdefault(pid, []).append(name)
    out = {}
    for p, f, e in rows:
        e = e or f
        lines = [f"Folder: {_root_relative(p.path_display.rsplit('/', 1)[0])}"]
        if e is not None and e.kind in ("event", "event_sub"):
            where = (f"{e.state}, USA" if e.state else "outside the US (the folder names the place)")
            when = e.event_date.isoformat() if e.event_date else "unknown date"
            lines.append(f"Event: {e.event_name or e.name} | {where} | folder date {when}")
        elif f is not None and f.kind in ("highlights", "highlights_sub"):
            lines.append(f"A {f.year or ''} highlights folder (no event recorded for this photo)".replace("  ", " "))
        if p.taken_at:
            camera = " ".join(x for x in (p.camera_make, p.camera_model) if x)
            lines.append(f"Taken: {p.taken_at:%Y-%m-%d %H:%M}" + (f" on a {camera}" if camera else ""))
        if p.lat is not None and p.lon is not None:
            near = ", ".join(x for x in (p.place_city, p.place_region, p.place_country) if x)
            lines.append(f"GPS: {p.lat:.4f}, {p.lon:.4f}" + (f" (near {near})" if near else ""))
        who = names.get(p.id)
        lines.append("People recognised, left to right: " + ", ".join(who) if who
                     else "People recognised: none")
        out[p.id] = "\n".join(lines)
    return out


def prepare(session: Session, source: PhotoSource, ids: list[int], workers: int = 8) -> list[Prepared]:
    """Images and context for `ids`; photos with no usable image are skipped (and logged)."""
    keys = display.render(session, source, ids)
    rows = session.execute(select(Photo.id, Photo.thumb_key, Photo.rotation).where(Photo.id.in_(ids))).all()
    info = {r.id: r for r in rows}
    ctx = contexts(session, ids)

    def load(pid: int) -> Prepared | None:
        for key in filter(None, (keys.get(pid), info[pid].thumb_key)):
            try:
                return Prepared(pid, info[pid].rotation, _image(storage.get_bytes(key)), ctx[pid])
            except Exception:  # noqa: BLE001  try the thumbnail
                log.warning("tag: can't load %s for photo %d", key, pid, exc_info=True)
        return None

    with ThreadPoolExecutor(workers) as pool:
        return [p for p in pool.map(load, ids) if p is not None]


def params(model: str, item: Prepared) -> dict:
    spec = MODELS[model]
    extra = {k: dict(v) for k, v in spec.params.items()}
    output_config = extra.pop("output_config", {}) | {"format": {"type": "json_schema", "schema": SCHEMA}}
    return dict(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(item.image).decode()}},
            {"type": "text", "text": item.context},
        ]}],
        output_config=output_config,
        **extra,
    )
