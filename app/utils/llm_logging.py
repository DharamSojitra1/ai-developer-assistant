"""Log every LLM call and tool call made through LangChain.

``install_llm_logging()`` registers ``LLMCallLogger`` as a LangChain
configure hook whose context variable defaults to the handler, so it is
attached to every chat model and tool run in the process (agent, RAG chat
chain, answerability check) without passing callbacks around. Each record
includes the request ID, agent run ID, and user ID bound in
``app.utils.log_context``.

Prompts, answers, and tool outputs are never logged, only metadata.
"""

import logging
import threading
import time
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.tracers.context import register_configure_hook

from app.config import LOG_REDACT_TOOL_ARGS
from app.tools.tool_result import parse_tool_result
from app.utils.log_context import get_log_context
from app.utils.redaction import redact_tool_args
from app.utils.request_metrics import current_request_metrics

llm_logger = logging.getLogger("agent.llm")
tool_logger = logging.getLogger("agent.tools")

# Set on an exception raised inside a LangGraph node: the node's name.
AGENT_STEP_ATTR = "agent_step"


def _elapsed_ms(started: float | None) -> int | None:
    if started is None:
        return None

    return round((time.perf_counter() - started) * 1000)


def _tool_status(output: Any) -> str:
    if isinstance(output, ToolMessage):
        if output.status == "error":
            return "error"
        output = output.content

    payload = parse_tool_result(output) if isinstance(output, str) else None

    if payload is not None and not payload["ok"]:
        return "error"

    return "success"


class LLMCallLogger(BaseCallbackHandler):
    # Logging is cheap; running inline keeps the caller's context variables
    # and avoids a thread-pool hop per callback.
    run_inline = True
    ignore_retriever = True
    # Not ignore_agent: LangChain gates tool callbacks on that flag too.
    # Chain callbacks are needed to know which graph node an error came from.

    def __init__(self):
        self._lock = threading.Lock()
        self._llm_runs: dict[UUID, tuple[float, str | None, int]] = {}
        self._tool_runs: dict[UUID, tuple[float, str, Any]] = {}
        self._node_runs: dict[UUID, str] = {}

    # ---------------------------------------------------------- graph steps

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: Any,
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        node = (metadata or {}).get("langgraph_node")

        if node:
            with self._lock:
                self._node_runs[run_id] = node

    def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            self._node_runs.pop(run_id, None)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            node = self._node_runs.pop(run_id, None)

        # The innermost failing run reports first, so keep the first tag.
        if node and getattr(error, AGENT_STEP_ATTR, None) is None:
            try:
                setattr(error, AGENT_STEP_ATTR, node)
            except AttributeError:
                pass

    # ------------------------------------------------------------ LLM calls

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        invocation_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        params = invocation_params or {}
        model = params.get("model") or params.get("model_name")
        message_count = len(messages[0]) if messages else 0

        with self._lock:
            self._llm_runs[run_id] = (time.perf_counter(), model, message_count)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            started, model, message_count = self._llm_runs.pop(
                run_id, (None, None, None)
            )

        message = None
        try:
            generation = response.generations[0][0]
            if isinstance(generation, ChatGeneration):
                message = generation.message
        except IndexError:
            pass

        usage = getattr(message, "usage_metadata", None) or {}
        metadata = getattr(message, "response_metadata", None) or {}

        request_metrics = current_request_metrics()
        if request_metrics is not None:
            request_metrics.record_llm_call(
                usage.get("input_tokens"),
                usage.get("output_tokens"),
            )

        llm_logger.info(
            "LLM call completed",
            extra={
                **get_log_context(),
                "model": metadata.get("model_name") or model,
                "latency_ms": _elapsed_ms(started),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "message_count": message_count,
                "tool_call_count": (
                    len(message.tool_calls) if isinstance(message, AIMessage) else 0
                ),
                "finish_reason": metadata.get("finish_reason"),
            },
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            started, model, message_count = self._llm_runs.pop(
                run_id, (None, None, None)
            )

        llm_logger.warning(
            "LLM call failed",
            extra={
                **get_log_context(),
                "model": model,
                "latency_ms": _elapsed_ms(started),
                "message_count": message_count,
                "error_type": type(error).__name__,
            },
        )

    # ----------------------------------------------------------- tool calls

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "unknown"

        with self._lock:
            self._tool_runs[run_id] = (
                time.perf_counter(),
                name,
                inputs if inputs is not None else input_str,
            )

    def _log_tool(self, run_id: UUID, status: str, **fields: Any) -> None:
        with self._lock:
            started, name, args = self._tool_runs.pop(
                run_id, (None, "unknown", None)
            )

        log = tool_logger.info if status == "success" else tool_logger.warning
        log(
            "Agent tool executed",
            extra={
                **get_log_context(),
                "tool_name": name,
                "tool_args": (
                    redact_tool_args(args) if LOG_REDACT_TOOL_ARGS else args
                ),
                "tool_status": status,
                "latency_ms": _elapsed_ms(started),
                **fields,
            },
        )

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._log_tool(run_id, _tool_status(output))

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._log_tool(run_id, "error", error_type=type(error).__name__)


llm_call_logger = LLMCallLogger()

_logger_var: ContextVar[LLMCallLogger | None] = ContextVar(
    "llm_call_logger",
    default=llm_call_logger,
)
_installed = False
_install_lock = threading.Lock()


def install_llm_logging() -> None:
    """Attach ``llm_call_logger`` to every LangChain run (idempotent)."""
    global _installed

    with _install_lock:
        if _installed:
            return

        register_configure_hook(_logger_var, inheritable=True)
        _installed = True
