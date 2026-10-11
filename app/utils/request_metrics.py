"""Per-request aggregation of LLM usage.

The middleware binds one ``RequestMetrics`` per request. Because context
variables are copied by reference into tasks and threads, LLM callbacks
anywhere in the request (agent nodes, tools, RAG) add to the same object,
and the middleware reads the totals once the response has been sent.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from app.utils.log_context import user_id_var


@dataclass
class RequestMetrics:
    user_id: str | None = None
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
        compare=False,
    )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def record_llm_call(
        self,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        # Callbacks for sync LLM calls run in worker threads.
        with self._lock:
            self.llm_calls += 1
            self.input_tokens += input_tokens or 0
            self.output_tokens += output_tokens or 0


request_metrics_var: ContextVar[RequestMetrics | None] = ContextVar(
    "request_metrics",
    default=None,
)


def current_request_metrics() -> RequestMetrics | None:
    return request_metrics_var.get()


@contextmanager
def bind_request_metrics(metrics: RequestMetrics) -> Iterator[RequestMetrics]:
    token = request_metrics_var.set(metrics)

    try:
        yield metrics
    finally:
        request_metrics_var.reset(token)


def bind_request_user(user_id: str) -> None:
    """Attribute the current request (logs and token usage) to a user.

    Called from the auth dependency, which runs in the request's own
    context, so the value is scoped to that request and needs no reset.
    """
    user_id_var.set(user_id)

    metrics = current_request_metrics()
    if metrics is not None:
        metrics.user_id = user_id
