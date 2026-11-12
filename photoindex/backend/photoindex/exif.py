"""Extract the EXIF fields we index from the first chunk of an image file."""

import io
import logging
from dataclasses import dataclass
from datetime import datetime

import exifread

logging.getLogger("exifread").setLevel(logging.ERROR)


@dataclass
class ExifInfo:
    taken_at: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    width: int | None = None
    height: int | None = None


def _ratio(v) -> float:
    return float(v.num) / float(v.den) if v.den else 0.0


def _gps(tags: dict, coord: str, ref: str) -> float | None:
    val, hemi = tags.get(f"GPS {coord}"), tags.get(f"GPS {ref}")
    if not val or len(val.values) < 3:
        return None
    d, m, s = (_ratio(x) for x in val.values[:3])
    deg = d + m / 60 + s / 3600
    if hemi and str(hemi.values).upper().startswith(("S", "W")):
        deg = -deg
    return round(deg, 6)


def _int(tags: dict, *names: str) -> int | None:
    for n in names:
        if n in tags:
            try:
                return int(str(tags[n].values[0]) if isinstance(tags[n].values, list) else str(tags[n]))
            except (ValueError, IndexError):
                pass
    return None


def parse_exif(head: bytes) -> ExifInfo:
    tags = exifread.process_file(io.BytesIO(head), details=False, strict=False)
    info = ExifInfo()
    for name in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
        raw = str(tags.get(name, "")).strip()
        if raw:
            try:
                info.taken_at = datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S")
                break
            except ValueError:
                continue
    info.lat = _gps(tags, "GPSLatitude", "GPSLatitudeRef")
    info.lon = _gps(tags, "GPSLongitude", "GPSLongitudeRef")
    if info.lat == 0.0 and info.lon == 0.0:  # common "no fix" placeholder
        info.lat = info.lon = None
    info.camera_make = str(tags["Image Make"]).strip() if "Image Make" in tags else None
    info.camera_model = str(tags["Image Model"]).strip() if "Image Model" in tags else None
    info.width = _int(tags, "EXIF ExifImageWidth", "Image ImageWidth")
    info.height = _int(tags, "EXIF ExifImageLength", "Image ImageLength")
    return info
