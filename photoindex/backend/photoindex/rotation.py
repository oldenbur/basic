"""Turn a photo upright in the app: its thumbnail and display copies are rotated and stored under new keys, face
boxes are moved to match, and faces are detected again on the upright image (names carry over by position).
The file in Dropbox is not changed."""

import io

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from photoindex import storage
from photoindex.models import Face, Photo


def rotate_jpeg(data: bytes, degrees: int) -> bytes:
    """Rotate JPEG bytes clockwise by a multiple of 90 degrees."""
    if not degrees % 360:
        return data
    with Image.open(io.BytesIO(data)) as im:
        turned = im.convert("RGB").rotate(-degrees, expand=True)  # PIL turns counter-clockwise
    buf = io.BytesIO()
    turned.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def rotate_box(x: float, y: float, w: float, h: float, degrees: int) -> tuple[float, float, float, float]:
    """A box in image fractions after turning the image clockwise."""
    match degrees % 360:
        case 90:
            return 1 - (y + h), x, h, w
        case 180:
            return 1 - (x + w), 1 - (y + h), w, h
        case 270:
            return y, 1 - (x + w), h, w
    return x, y, w, h


def set_rotation(session: Session, photo: Photo, rotation: int) -> bool:
    """Make `rotation` (clockwise degrees from how Dropbox renders the file) the photo's orientation. Commits.
    Returns False if nothing changed."""
    rotation %= 360
    if rotation not in (0, 90, 180, 270):
        raise ValueError("rotation must be 0, 90, 180 or 270")
    delta = (rotation - photo.rotation) % 360
    if not delta:
        return False
    for attr, make_key in (("thumb_key", storage.thumb_key), ("display_key", storage.display_key)):
        old = getattr(photo, attr)
        if old is None:
            continue
        new = make_key(photo.id, rotation)
        storage.put_image(new, rotate_jpeg(storage.get_bytes(old), delta))
        setattr(photo, attr, new)
    for face in session.scalars(select(Face).where(Face.photo_id == photo.id)):
        face.x, face.y, face.w, face.h = rotate_box(face.x, face.y, face.w, face.h, delta)
    photo.rotation = rotation
    if photo.face_status == "done":
        photo.face_status = "pending"  # sideways faces are often missed: look again
    session.commit()
    return True
