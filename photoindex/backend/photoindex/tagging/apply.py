"""Put a model's answer onto a photo: caption, score, tags, place, and (when the model is sure) an upright turn.
Your own tag edits are kept: a tag you removed stays removed, a tag you added stays."""

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from photoindex.models import Photo, PhotoAI, PhotoTag, Tag
from photoindex.rotation import set_rotation
from photoindex.tagging.vocab import normalize, tags_from


def resolve_tag(session: Session, category: str, value: str, create: bool = True) -> Tag | None:
    """The tag for (category, value), case-insensitively, following merges."""
    tag = session.scalars(select(Tag).where(Tag.category == category, func.lower(Tag.value) == value.lower())).first()
    if tag is None:
        if not create:
            return None
        tag = Tag(category=category, value=value)
        session.add(tag)
        session.flush()
    seen = set()
    while tag.merged_into_id is not None and tag.id not in seen:
        seen.add(tag.id)
        tag = session.get(Tag, tag.merged_into_id)
    return tag


def refresh_terms(session: Session, photo: Photo) -> None:
    """Rebuild the words text search matches for this photo (caption, tags, place)."""
    result = session.get(PhotoAI, photo.ai_id).result if photo.ai_id else {}
    words = [photo.caption, photo.scene, photo.setting, photo.place_country, photo.place_region, photo.place_city]
    loc = (result or {}).get("location") or {}
    words.append(loc.get("place_name"))
    for v in (result or {}).get("vehicles") or []:
        words += [v.get("color"), v.get("type")]
    words += session.scalars(
        select(Tag.value).join(PhotoTag, PhotoTag.tag_id == Tag.id)
        .where(PhotoTag.photo_id == photo.id, ~PhotoTag.removed, ~Tag.hidden)
    ).all()
    photo.ai_terms = " ".join(w for w in words if w) or None


def set_tags(session: Session, photo_id: int, tag_ids: list[int]) -> None:
    """Make the AI's tags for a photo exactly `tag_ids`, leaving your additions and removals alone."""
    mine = set(session.scalars(select(PhotoTag.tag_id).where(PhotoTag.photo_id == photo_id, PhotoTag.source == "user")))
    session.execute(delete(PhotoTag).where(PhotoTag.photo_id == photo_id, PhotoTag.source == "ai",
                                           PhotoTag.tag_id.not_in(tag_ids or [0])))
    rows = [dict(photo_id=photo_id, tag_id=t, source="ai") for t in dict.fromkeys(tag_ids) if t not in mine]
    if rows:
        session.execute(insert(PhotoTag).values(rows).on_conflict_do_nothing())


def _place(photo: Photo, loc: dict) -> None:
    if not loc or loc.get("confidence") not in ("medium", "high"):
        return
    if photo.place_source in (None, "ai") and loc.get("country"):
        photo.place_country = loc["country"] or None
        photo.place_region = loc.get("region") or None
        photo.place_city = loc.get("city") or None
        photo.place_source = "ai"
    elif (photo.place_source == "folder" and not photo.place_city and loc.get("city")
          and (loc.get("region") or "").lower() == (photo.place_region or "").lower()):
        photo.place_city = loc["city"]  # the folder knew the state; the AI adds the town


def apply(session: Session, photo: Photo, ai: PhotoAI, rotate: bool = True) -> None:
    """Apply `ai` (a finished answer) to `photo` and to the photos that copy it. Commits."""
    r = ai.result or {}
    targets = [photo] + list(session.scalars(select(Photo).where(Photo.tag_source_id == photo.id,
                                                                  Photo.tag_status == "follower")))
    tag_ids = [resolve_tag(session, c, v).id for c, v in tags_from(r)]
    for p in targets:
        p.ai_id = ai.id
        p.caption = (r.get("caption") or "").strip() or None
        p.scene = normalize("scene", r.get("scene") or "")
        p.setting = r.get("setting")
        a = r.get("aesthetic")
        p.aesthetic = max(1, min(10, int(a))) if isinstance(a, int | float) else None
        _place(p, r.get("location") or {})
        set_tags(session, p.id, tag_ids)
        refresh_terms(session, p)
        if p is photo:
            p.tag_status = "done"
            p.error = None
    session.commit()
    turn = r.get("rotation") or 0
    if rotate and turn in (90, 180, 270) and r.get("confidence") != "low":
        upright = (ai.base_rotation + turn) % 360
        for p in targets:
            set_rotation(session, p, upright)
