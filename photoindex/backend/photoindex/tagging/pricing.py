"""The models the pilot compares, how each is called, and what a request costs.

Prices are list prices per million tokens (Claude API, November 2026). The Batch API bills half of them. Check them
against https://www.anthropic.com/pricing when they change; the pilot's report uses the real token counts from each
result, so only the dollar rates here can drift.
"""

from dataclasses import dataclass, field

BATCH_DISCOUNT = 0.5
CACHE_WRITE = 1.25  # 5-minute cache writes cost 1.25x input


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    input: float  # $/MTok
    output: float
    cache_read: float
    # Extra request parameters: thinking off where the model allows it, low effort. Tagging a photo is a quick
    # look, not a reasoning task. (Opus 5.5 always thinks; effort is the only dial.)
    params: dict = field(default_factory=dict)
    # Rough tokens per photo before the pilot has measured them.
    est_input: int = 2600
    est_output: int = 450


MODELS: dict[str, ModelSpec] = {m.id: m for m in (
    ModelSpec("claude-haiku-5-5", "Haiku 5.5", 0.10, 0.50, 0.01,
              {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}),
    ModelSpec("claude-sonnet-5-5", "Sonnet 5.5", 2.00, 10.00, 0.20,
              {"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}}),
    ModelSpec("claude-opus-5-5", "Opus 5.5", 4.00, 20.00, 0.20,
              {"thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}}, est_output=900),
)}
DEFAULT_MODEL = "claude-opus-5-5"


def cost(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0,
         batch: bool = True) -> float:
    m = MODELS[model]
    usd = (input_tokens * m.input + cache_write * m.input * CACHE_WRITE + cache_read * m.cache_read
           + output_tokens * m.output) / 1e6
    return usd * (BATCH_DISCOUNT if batch else 1)


def estimate(model: str, photos: int, per_photo: float | None = None) -> float:
    """Dollar estimate for tagging `photos` photos; `per_photo` is a measured average when one exists."""
    if per_photo is None:
        m = MODELS[model]
        per_photo = cost(model, m.est_input, m.est_output)
    return photos * per_photo
