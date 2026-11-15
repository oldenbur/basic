from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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

    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_photos_folder_taken", "folder_id", "taken_at"),)


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
