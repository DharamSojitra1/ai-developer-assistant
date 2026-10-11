"""Latency and token usage measurement for evaluation runs."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from langchain_core.callbacks import get_usage_metadata_callback

from evals.pricing import estimate_cost


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "ModelUsage") -> "ModelUsage":
        return ModelUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True)
class RunUsage:
    """Wall-clock latency and chat-model token usage of one measured block."""

    latency_seconds: float = 0.0
    models: dict[str, ModelUsage] = field(default_factory=dict)

    @property
    def input_tokens(self) -> int:
        return sum(usage.input_tokens for usage in self.models.values())

    @property
    def output_tokens(self) -> int:
        return sum(usage.output_tokens for usage in self.models.values())

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float | None:
        return estimate_cost(self.models)

    def __add__(self, other: "RunUsage") -> "RunUsage":
        models = dict(self.models)

        for name, usage in other.models.items():
            models[name] = models.get(name, ModelUsage()) + usage

        return RunUsage(
            latency_seconds=self.latency_seconds + other.latency_seconds,
            models=models,
        )

    def to_dict(self) -> dict:
        return {
            "latency_seconds": round(self.latency_seconds, 3),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "models": {
                name: {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                }
                for name, usage in self.models.items()
            },
        }


class UsageMeasurement:
    def __init__(self):
        self.usage = RunUsage()


@contextmanager
def measure_usage() -> Iterator[UsageMeasurement]:
    """Measure latency and tokens of every chat-model call inside the block.

    The usage callback is propagated through a context variable, so nested
    calls (e.g. the answerability check inside the RAG tool) are counted
    without passing callbacks around. The result is available on
    ``measurement.usage`` after the block exits, even if it raised.
    """
    measurement = UsageMeasurement()
    started = time.perf_counter()

    with get_usage_metadata_callback() as handler:
        try:
            yield measurement
        finally:
            measurement.usage = RunUsage(
                latency_seconds=time.perf_counter() - started,
                models={
                    model: ModelUsage(
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                    )
                    for model, usage in handler.usage_metadata.items()
                },
            )
