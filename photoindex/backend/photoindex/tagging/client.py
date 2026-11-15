"""The Anthropic client (swapped for a fake in tests)."""

from functools import lru_cache

import anthropic

from photoindex.config import get_settings


@lru_cache
def get_client() -> anthropic.Anthropic:
    key = get_settings().anthropic_api_key
    if not key:
        raise RuntimeError("Set ANTHROPIC_API_KEY in .env to tag photos")
    return anthropic.Anthropic(api_key=key, max_retries=4)
