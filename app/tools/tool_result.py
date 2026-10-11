import asyncio
import functools
import json
import time
from typing import Any

from pydantic import ValidationError

from app.config import TOOL_TIMEOUT_SECONDS
from app.utils.agent_logger import logger


UNEXPECTED_TOOL_ERROR = (
    "The tool failed unexpectedly. Try again or use a different approach."
)


def tool_success(result: Any) -> str:
    return json.dumps({"ok": True, "result": result, "error": None})


def tool_error(message: str) -> str:
    return json.dumps({"ok": False, "result": None, "error": message})


def handle_validation_error(exc: ValidationError) -> str:
    details = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    )

    return tool_error(f"Invalid tool input: {details}")


def handle_tool_exception(exc: Exception) -> str:
    # ToolNode infers which exceptions to catch from this annotation.
    # The details go to the logs only, never to the LLM.
    logger.error(
        "Tool raised an unexpected error",
        exc_info=exc,
    )

    return tool_error(UNEXPECTED_TOOL_ERROR)


def with_timeout(
    message: str,
    seconds: float = TOOL_TIMEOUT_SECONDS,
):
    """Cap an async tool's run time and return a structured error on timeout.

    Apply it below @tool. Blocking work inside the tool must run via
    asyncio.to_thread, otherwise the timeout cannot interrupt it.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            started = time.perf_counter()

            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=wrapper.timeout_seconds,
                )
            except TimeoutError:
                logger.warning(
                    "Tool timed out",
                    extra={
                        "tool_function": func.__name__,
                        "timeout_seconds": wrapper.timeout_seconds,
                        "elapsed_ms": round(
                            (time.perf_counter() - started) * 1000
                        ),
                    },
                )
                return tool_error(message)

        # Read at call time so it can be overridden without re-decorating.
        wrapper.timeout_seconds = seconds

        return wrapper

    return decorator


def parse_tool_result(content: Any) -> dict | None:
    """Return the {ok, result, error} payload, or None if content isn't one."""
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(payload, dict) or "ok" not in payload:
        return None

    return payload
