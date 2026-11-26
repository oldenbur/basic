from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (BigInteger, Boolean, Computed, Date, DateTime, Float, ForeignKey, Index, Integer, SmallInteger,
                        String, Text, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    dropbox_id: Mapped[str] = mapped_column(String, unique=True)
    path_lower: Mapped[str] = mapped_column(String, index=True)
    path_display: Mapped[str] = mapped_column(String)
    parent_path_lower: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), index=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Set by the parse stage. kind: year | event | highlights | event_sub | highlights_sub | ignored
    kind: Mapped[str | None] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    event_date: Mapped[date | None] = mapped_column(Date)
    state: Mapped[str | None] = mapped_column(String(8))
    event_name: Mapped[str | None] = mapped_column(String)
    event_folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"))
    # Lower-case words for text search: event name split on CamelCase, place, state code and name.
    search_terms: Mapped[str | None] = mapped_column(Text)
    parse_ok: Mapped[bool | None] = mapped_column(Boolean)
    issues: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    suggested_name: Mapped[str | None] = mapped_column(String)

    # Explicitly added to the processing set from the UI (applies to everything beneath it).
    in_scope: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    dropbox_id: Mapped[str] = mapped_column(String, unique=True)
    path_lower: Mapped[str] = mapped_column(String, index=True)
    path_display: Mapped[str] = mapped_column(String)
    parent_path_lower: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    size: Mapped[int | None] = mapped_column(BigInteger)
    client_modified: Mapped[datetime | None] = mapped_column(DateTime)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # In a folder that doesn't follow the naming scheme: kept in the index but never linked or processed.
    ignored: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # A single print in one of the scanned print albums (settings.album_folders). Still ignored by the library,
    # but thumbnailed and searched for faces so the albums can be dated and split into events.
    album_scan: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    album_event_id: Mapped[int | None] = mapped_column(ForeignKey("album_events.id", ondelete="SET NULL",
                                                                  use_alter=True), index=True)

    # Highlights: a copy in a highlights folder points at the canonical original it duplicates.
    is_highlight_copy: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    original_id: Mapped[int | None] = mapped_column(ForeignKey("photos.id", ondelete="SET NULL"), index=True)
    link_method: Mapped[str | None] = mapped_column(String)  # hash | stem | stem_time | none
    has_highlight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    in_processing_set: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    needs_meta: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # EXIF (meta stage)
    meta_status: Mapped[str] = mapped_column(String, default="pending", server_default="pending", index=True)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    camera_make: Mapped[str | None] = mapped_column(String)
    camera_model: Mapped[str | None] = mapped_column(String)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    burst_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    date_mismatch_days: Mapped[int | None] = mapped_column(Integer)

    # Thumbnails (thumbs stage)
    thumb_status: Mapped[str] = mapped_column(String, default="pending", server_default="pending", index=True)
    thumb_key: Mapped[str | None] = mapped_column(String)
    phash: Mapped[str | None] = mapped_column(String(16))
    # 2048px slideshow copy, made lazily on first view (or by "Prepare" on a theme).
    display_key: Mapped[str | None] = mapped_column(String)

    # Faces (faces stage), run on highlights
    face_status: Mapped[str] = mapped_column(String, default="pending", server_default="pending", index=True)
    face_count: Mapped[int | None] = mapped_column(Integer)

    # Where (places stage from GPS or the folder's state; the AI's guess fills in when neither says).
    place_country: Mapped[str | None] = mapped_column(String, index=True)
    place_region: Mapped[str | None] = mapped_column(String, index=True)
    place_city: Mapped[str | None] = mapped_column(String)
    place_source: Mapped[str | None] = mapped_column(String)  # gps | folder | ai

    # Clockwise turn applied to our thumbnail/display copies (the file in Dropbox is never changed).
    rotation: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")

    # AI tags (tag stage). tag_status: pending | queued | done | error | follower (copies tag_source_id's tags:
    # a burst shot or near-duplicate of a photo that was sent instead).
    tag_status: Mapped[str] = mapped_column(String, default="pending", server_default="pending", index=True)
    tag_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    tag_source_id: Mapped[int | None] = mapped_column(ForeignKey("photos.id", ondelete="SET NULL"))
    ai_id: Mapped[int | None] = mapped_column(ForeignKey("photo_ai.id", ondelete="SET NULL", use_alter=True))
    caption: Mapped[str | None] = mapped_column(Text)
    scene: Mapped[str | None] = mapped_column(String)
    setting: Mapped[str | None] = mapped_column(String)
    aesthetic: Mapped[int | None] = mapped_column(SmallInteger, index=True)
    # Caption, tags and place names, for text search (stemmed: "skiing" finds "skis").
    ai_terms: Mapped[str | None] = mapped_column(Text)
    ai_tsv = mapped_column(TSVECTOR, Computed("to_tsvector('english', coalesce(ai_terms, ''))", persisted=True))

    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_photos_folder_taken", "folder_id", "taken_at"),
        Index("ix_photos_ai_tsv", "ai_tsv", postgresql_using="gin"),
    )


class SyncState(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    cursor: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Theme(Base):
    """A saved search (photoindex.search.ThemeQuery) that can be played as a slideshow."""

    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    query: Mapped[dict] = mapped_column(JSONB)
    sort: Mapped[str] = mapped_column(String, default="event_shuffle", server_default="event_shuffle")
    cover_photo_id: Mapped[int | None] = mapped_column(ForeignKey("photos.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    cover_face_id: Mapped[int | None] = mapped_column(ForeignKey("faces.id", ondelete="SET NULL", use_alter=True))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Face(Base):
    """One detected face. Box coordinates are fractions (0-1) of the photo's display image."""

    __tablename__ = "faces"

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)
    size_px: Mapped[int] = mapped_column(Integer)  # shorter side of the box in display-image pixels
    det_score: Mapped[float] = mapped_column(Float)
    quality: Mapped[float] = mapped_column(Float)  # 0-1: size, sharpness, frontal-ness; best faces represent groups
    embedding: Mapped[list[float]] = mapped_column(Vector(512))
    crop_key: Mapped[str | None] = mapped_column(String)

    # Who it is. assigned_by: "user" (you said so) or "auto" (close match to faces you confirmed).
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), index=True)
    assigned_by: Mapped[str | None] = mapped_column(String)
    # A plausible but uncertain match, waiting in the review queue.
    suggested_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), index=True)
    suggested_score: Mapped[float | None] = mapped_column(Float)
    rejected_person_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, server_default="{}")
    # Group of similar unnamed faces from the last clustering run (the group's smallest face id).
    cluster_id: Mapped[int | None] = mapped_column(Integer, index=True)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # "not someone I care about"


class AppSetting(Base):
    """Small settings changed from the UI (e.g. the tagging model and daily spend cap)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)


class TagRun(Base):
    """One Message Batch: a pilot model's share of the pilot, or a slice of the backfill."""

    __tablename__ = "tag_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String)  # pilot | backfill
    model: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[int] = mapped_column(Integer)
    batch_id: Mapped[str | None] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="submitted", index=True)  # submitted | ended | failed
    requests: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    errored: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float)  # from the results' token usage
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class PhotoAI(Base):
    """One model's answer for one photo. The applied one is photos.ai_id; pilot answers stay for comparison."""

    __tablename__ = "photo_ai"

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("tag_runs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued | done | error | refused
    base_rotation: Mapped[int] = mapped_column(SmallInteger, default=0)  # photos.rotation when the image was sent
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    # Pilot review: you picked this answer as the best of the models, and/or flagged parts of it as wrong.
    best: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("run_id", "photo_id"),)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String)  # activity | scene | object | animal | gear | vehicle | landmark
    value: Mapped[str] = mapped_column(String)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Merged into another tag: new AI answers with this value land on that tag instead.
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id", ondelete="SET NULL"))

    __table_args__ = (UniqueConstraint("category", "value"),)


class PhotoTag(Base):
    __tablename__ = "photo_tags"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True)
    # "ai", or "user" when you added it or removed it; your edits survive re-tagging.
    source: Mapped[str] = mapped_column(String, default="ai")
    removed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class AlbumEvent(Base):
    """A run of consecutive prints in a scanned album that look like one event (one roll, one occasion)."""

    __tablename__ = "album_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    album: Mapped[str] = mapped_column(String, index=True)  # folder name, e.g. albums3
    seq: Mapped[int] = mapped_column(Integer)  # position in the album, from 1
    size: Mapped[int] = mapped_column(Integer)
    first_name: Mapped[str] = mapped_column(String)  # file names of its first and last prints
    last_name: Mapped[str] = mapped_column(String)
    # Why it starts here: the strongest signals at the boundary before it (colour, print size, page, people).
    break_reasons: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    break_score: Mapped[float | None] = mapped_column(Float)
    # Who is in it: person id -> number of prints with a confident match ({"12": 3}).
    people: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    has_me: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # settings.album_me
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("album", "seq"),)


class AlbumFace(Base):
    """A face in an album print. Kept apart from `faces` so childhood photos never land on the People pages
    (or get matched to look-alike children of the next generation). Matched against the faces you named there."""

    __tablename__ = "album_faces"

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    # Clockwise turn applied to the print before detection (prints scanned sideways); the box is in that frame.
    rotation: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)
    size_px: Mapped[int] = mapped_column(Integer)
    det_score: Mapped[float] = mapped_column(Float)
    quality: Mapped[float] = mapped_column(Float)
    embedding: Mapped[list[float]] = mapped_column(Vector(512))
    crop_key: Mapped[str | None] = mapped_column(String)
    # Closest named person and how close (cosine, top-3 mean); `person_id` is set only when you confirm.
    match_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), index=True)
    match_score: Mapped[float | None] = mapped_column(Float)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), index=True)
    # Group of similar unnamed album faces (its smallest face id), so childhood faces can be named a group at a time.
    cluster_id: Mapped[int | None] = mapped_column(Integer, index=True)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # no one to name


class AlbumRef(Base):
    """Something recognisable that pins prints to a period: a house you lived in, a grandparent's home, a school,
    a trip. Its example prints go to the dating model as reference images."""

    __tablename__ = "album_refs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String)  # home | family | school | trip | other
    label: Mapped[str] = mapped_column(String, unique=True)
    # When it applies (a house: the years you lived there; a trip: its month). Either end may be open.
    start: Mapped[date | None] = mapped_column(Date)
    end: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)  # what to look for, e.g. "white colonial, black shutters"
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AlbumRefExample(Base):
    """A print that shows a reference. Proposed ones wait for you; only confirmed ones are used."""

    __tablename__ = "album_ref_examples"

    ref_id: Mapped[int] = mapped_column(ForeignKey("album_refs.id", ondelete="CASCADE"), primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String, default="proposed")  # proposed | confirmed | rejected
    source: Mapped[str] = mapped_column(String, default="user")  # user | claude
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AlbumDateRun(Base):
    """One Message Batch of album events sent for dating (a pilot, or the full run)."""

    __tablename__ = "album_date_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String)  # pilot | full
    model: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[int] = mapped_column(Integer)
    batch_id: Mapped[str | None] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="submitted", index=True)  # submitted|collecting|ended|failed
    requests: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    errored: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class AlbumDateAnswer(Base):
    """The model's answer for one event (a run of prints). Keyed by the prints it covered, not the event id:
    events are rebuilt when the albums are regrouped."""

    __tablename__ = "album_date_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("album_date_runs.id", ondelete="CASCADE"), index=True)
    album: Mapped[str] = mapped_column(String)
    event_seq: Mapped[int] = mapped_column(Integer)  # the event's position when it was sent
    photo_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer))  # in album order
    status: Mapped[str] = mapped_column(String, default="queued")  # queued | done | error | refused
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AlbumPrintDate(Base):
    """The model's dating of one print, from its event's answer. The latest answer for a print wins."""

    __tablename__ = "album_print_dates"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("album_date_answers.id", ondelete="CASCADE"), index=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    best: Mapped[date | None] = mapped_column(Date)  # first of the month
    earliest: Mapped[date | None] = mapped_column(Date)
    latest: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[str | None] = mapped_column(String)  # low | medium | high
    ref_label: Mapped[str | None] = mapped_column(String)
    ages: Mapped[list | None] = mapped_column(JSONB)  # [{"name": ..., "age": 7.5}]
    different_occasion: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    caption: Mapped[str | None] = mapped_column(Text)
    clues: Mapped[str | None] = mapped_column(Text)


class AlbumPlacement(Base):
    """Where an album print goes: its settled month and whether it's copied into that year's folder."""

    __tablename__ = "album_placements"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[date] = mapped_column(Date, index=True)  # first of the month
    # model (its own estimate) | event (its event's month) | neighbours (pulled between confident neighbours)
    # | reference (kept inside a matched reference's dates) | you (set by hand; never recomputed)
    source: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)  # include | older | review | skip
    reason: Mapped[str | None] = mapped_column(Text)
    answer_id: Mapped[int | None] = mapped_column(ForeignKey("album_date_answers.id", ondelete="SET NULL"), index=True)
    has_me: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    event_key: Mapped[str | None] = mapped_column(String, index=True)  # "a{answer id}" or "g{group id}"
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AlbumGroup(Base):
    """An event you made by splitting prints off another one (its key is "g{id}")."""

    __tablename__ = "album_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    album: Mapped[str] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AlbumPrintMove(Base):
    """A print you moved out of the event that dated it: into another dated event, or into one of your groups."""

    __tablename__ = "album_print_moves"

    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True)
    answer_id: Mapped[int | None] = mapped_column(ForeignKey("album_date_answers.id", ondelete="CASCADE"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("album_groups.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AlbumEventOverride(Base):
    """Your decision and month for an event ("a{answer id}" or "g{group id}"); kept when placement reruns."""

    __tablename__ = "album_event_overrides"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str | None] = mapped_column(String)  # include | skip
    month: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
