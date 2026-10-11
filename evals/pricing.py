"""USD prices per million tokens, used to estimate evaluation cost.

Prices change: check https://groq.com/pricing before relying on totals.
A model missing from this table makes the cost estimate None rather than
silently zero. Embedding calls (Gemini) are not chat-model calls, so their
tokens are not captured and are not included.
"""

from collections.abc import Mapping
from typing import Protocol


class TokenCounts(Protocol):
    input_tokens: int
    output_tokens: int


# model name -> (input price, output price) in USD per million tokens
PRICES_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.15, 0.75),
}


def estimate_cost(
    usage_by_model: Mapping[str, TokenCounts],
    prices: Mapping[str, tuple[float, float]] = PRICES_PER_MILLION_TOKENS,
) -> float | None:
    """Total USD cost, or None if any model used has no known price."""
    total = 0.0

    for model, usage in usage_by_model.items():
        if model not in prices:
            return None

        input_price, output_price = prices[model]
        total += (
            usage.input_tokens * input_price
            + usage.output_tokens * output_price
        ) / 1_000_000

    return total


def unpriced_models(
    usage_by_model: Mapping[str, TokenCounts],
    prices: Mapping[str, tuple[float, float]] = PRICES_PER_MILLION_TOKENS,
) -> list[str]:
    return sorted(model for model in usage_by_model if model not in prices)
