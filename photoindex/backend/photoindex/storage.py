"""S3-compatible image store (MinIO in dev, Cloudflare R2 in production)."""

from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from photoindex.config import get_settings


@lru_cache
def _client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "adaptive"}),
    )


def ensure_bucket() -> None:
    bucket = get_settings().s3_bucket
    try:
        _client().head_bucket(Bucket=bucket)
    except ClientError:
        _client().create_bucket(Bucket=bucket)


def put_image(key: str, data: bytes) -> None:
    _client().put_object(
        Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType="image/jpeg",
        CacheControl="public, max-age=31536000, immutable",
    )


def get_bytes(key: str) -> bytes:
    return _client().get_object(Bucket=get_settings().s3_bucket, Key=key)["Body"].read()


def exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=get_settings().s3_bucket, Key=key)
        return True
    except ClientError:
        return False


def image_url(key: str, expires: int = 6 * 3600) -> str:
    s = get_settings()
    if s.public_image_base:
        return f"{s.public_image_base.rstrip('/')}/{key}"
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": s.s3_bucket, "Key": key}, ExpiresIn=expires
    )


# A rotated copy gets its own key, so browsers and the CDN never serve the old orientation from cache.
def _rot(rotation: int) -> str:
    return f"-r{rotation}" if rotation % 360 else ""


def thumb_key(photo_id: int, rotation: int = 0) -> str:
    return f"thumbs/640/{photo_id}{_rot(rotation)}.jpg"


def display_key(photo_id: int, rotation: int = 0) -> str:
    return f"display/2048/{photo_id}{_rot(rotation)}.jpg"


def face_key(face_id: int) -> str:
    return f"faces/160/{face_id}.jpg"
