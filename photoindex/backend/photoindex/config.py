from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://photoindex:photoindex@localhost:5432/photoindex"

    # Photo source: "dropbox" for the real library, "local" for a directory on disk (dev/tests).
    source: str = "dropbox"
    dropbox_app_key: str = ""
    dropbox_app_secret: str = ""
    dropbox_refresh_token: str = ""
    photo_root: str = "/Photos"  # Dropbox path, or a local directory when source=local

    # S3-compatible image store: SeaweedFS in dev, Cloudflare R2 in production.
    s3_endpoint_url: str = "http://localhost:8333"
    s3_access_key: str = "dev"
    s3_secret_key: str = "dev"
    s3_bucket: str = "photoindex"
    s3_region: str = "auto"
    # When set (e.g. an R2 custom domain), image URLs are public CDN URLs instead of presigned ones.
    public_image_base: str | None = None

    workers: int = 8
    models_dir: str = "~/.cache/photoindex/models"  # face models, downloaded on first use
    exif_head_bytes: int = 128 * 1024

    # AI tagging (Claude Message Batches API). The model and daily spend cap are chosen in the UI.
    anthropic_api_key: str = ""
    tag_batch_size: int = 500  # photos per batch: ~150KB of image each, well under the 256MB batch limit
    tag_max_open_batches: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
