"""Per-request and per-run logging context carried by context variables.

Values bound here follow the code path across ``await``, asyncio tasks
(LangGraph nodes), and ``asyncio.to_thread``, so logs written deep inside
the agent, tools, or services carry the request ID and agent run ID
without passing them through every function.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

_CONTEXT_VARS = {
    "request_id": request_id_var,
    "run_id": run_id_var,
    "user_id": user_id_var,
}


def get_log_context() -> dict[str, str]:
    """The bound context values, omitting unset ones."""
    return {
        name: value
        for name, var in _CONTEXT_VARS.items()
        if (value := var.get()) is not None
    }


@contextmanager
def bind_log_context(**values: str | None) -> Iterator[None]:
    unknown = set(values) - set(_CONTEXT_VARS)
    if unknown:
        raise ValueError(f"Unknown log context fields: {sorted(unknown)}")

    tokens = [
        (_CONTEXT_VARS[name], _CONTEXT_VARS[name].set(value))
        for name, value in values.items()
    ]

    try:
        yield
    finally:
        for var, token in reversed(tokens):
            try:
                var.reset(token)
            except ValueError:
                # An async generator closed from another context (e.g. a
                # cancelled stream) cannot reset; that context is discarded.
                pass


_ERROR_CONTEXT_ATTR = "log_context"


def mark_error_logged(exc: BaseException, **fields: str | None) -> None:
    """Record that ``exc`` was already logged, with context such as run_id.

    App-level exception handlers use this to add the run ID and step to
    their log without repeating the traceback.
    """
    try:
        setattr(exc, _ERROR_CONTEXT_ATTR, {**get_log_context(), **fields})
    except AttributeError:
        pass


def logged_error_context(exc: BaseException) -> dict | None:
    """The context recorded by ``mark_error_logged``, or None if not logged."""
    return getattr(exc, _ERROR_CONTEXT_ATTR, None)


class LogContextFilter(logging.Filter):
    """Adds the bound context to every record that passes the handler.

    Values passed explicitly via ``extra`` take precedence.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for name, value in get_log_context().items():
            if not hasattr(record, name):
                setattr(record, name, value)

        return True
