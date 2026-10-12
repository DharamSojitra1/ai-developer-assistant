import time
import uuid

from langchain_core.messages import AIMessageChunk
from langgraph.types import Command

from app.config import (
    AGENT_HISTORY_LIMIT,
    AGENT_MAX_TOKENS,
    AGENT_TEMPERATURE,
)
from app.database import get_recent_chat_history, save_chat_history
from app.agents.calculator_agent import FINAL_ANSWER_TAG
from app.agents.checkpoints import get_checkpointer, run_config
from app.agents.orchestrator import create_orchestrator_graph
from app.guards.injection import detect_injection, screen_input
from app.tools.registry import ROLE_USER
from app.utils.agent_logger import logger
from app.utils.llm_logging import AGENT_STEP_ATTR
from app.utils.log_context import (
    bind_log_context,
    get_log_context,
    mark_error_logged,
)

# Steps outside the graph; failures inside it report the graph node instead.
STEP_LOAD_HISTORY = "load_history"
STEP_GRAPH = "graph"
STEP_SAVE_HISTORY = "save_history"

STATUS_COMPLETED = "completed"
STATUS_AWAITING_APPROVAL = "awaiting_approval"


class RunNotFoundError(LookupError):
    """No run with this ID belongs to the user (or it has expired)."""


class RunNotPendingError(RuntimeError):
    """The run exists but is not waiting for an approval."""


def approval_url(run_id: str) -> str:
    return f"/api/agent/runs/{run_id}/approval"


async def build_agent_messages(
    user_id: str,
    message: str,
    limit: int = AGENT_HISTORY_LIMIT,
    conversation_id: str | None = None,
) -> list:

    history = await get_recent_chat_history(
        user_id=user_id,
        limit=limit,
        conversation_id=conversation_id,
    )

    messages = []

    for item in history:
        messages.append(
            ("human", item["message"])
        )

        messages.append(
            ("ai", item["response"])
        )

    messages.append(
        ("human", message)
    )

    return messages


def build_initial_state(
    messages: list,
    run_id: str | None = None,
    started_at: float | None = None,
    user_id: str | None = None,
    user_message: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    return {
        "messages": messages,
        "conversation_id": conversation_id or str(uuid.uuid4()),
        "iteration_count": 0,
        "sources": [],
        "tool_calls": [],
        "run_id": run_id or str(uuid.uuid4()),
        "started_at": started_at or time.time(),
        "stop_reason": "",
        "user_id": user_id or "",
        "user_message": user_message or "",
        "route": "",
        "approvals": {},
        "findings": [],
        "supervisor_rounds": 0,
    }


def create_run_graph(role: str):
    return create_orchestrator_graph(
        role=role,
        temperature=AGENT_TEMPERATURE,
        max_tokens=AGENT_MAX_TOKENS,
        checkpointer=get_checkpointer(),
    )


async def pending_approvals(graph, run_id: str) -> list[dict]:
    """Actions the paused run is waiting on; empty when it is not paused."""
    snapshot = await graph.aget_state(run_config(run_id))

    return [
        action
        for interrupt in snapshot.interrupts
        if isinstance(interrupt.value, dict)
        and interrupt.value.get("type") == "approval_required"
        for action in interrupt.value.get("actions", [])
    ]


def approval_message(run_id: str, actions: list[dict]) -> str:
    targets = ", ".join(
        f"'{action.get('source') or action['document_id']}'"
        for action in actions
    )

    return (
        f"Approval needed: I want to delete the document {targets}. "
        f"Approve or reject it with POST {approval_url(run_id)}."
    )


def log_run_started(
    user_id: str,
    message: str,
    state: dict,
    role: str,
) -> None:
    logger.info(
        "Agent execution started",
        extra={
            **get_log_context(),
            "user_id": user_id,
            "run_id": state["run_id"],
            "role": role,
            "message_length": len(message),
        },
    )


def log_run_awaiting_approval(user_id: str, result: dict, actions: list) -> None:
    logger.info(
        "Agent execution awaiting approval",
        extra={
            **get_log_context(),
            "user_id": user_id,
            "run_id": result.get("run_id"),
            "route": result.get("route"),
            "pending_actions": [
                {"action": a.get("action"), "document_id": a.get("document_id")}
                for a in actions
            ],
        },
    )


def log_run_completed(
    user_id: str,
    message: str,
    result: dict,
    injection_flags: list[str] | None = None,
) -> None:
    # Each tool call is logged as it runs (with latency) by
    # app.utils.llm_logging; this summary also covers calls the graph
    # rejected without running, such as a tool outside the user's role.
    tool_calls = result.get("tool_calls", [])
    started_at = result.get("started_at")
    ended_at = time.time()

    logger.info(
        "Agent execution completed",
        extra={
            **get_log_context(),
            "user_id": user_id,
            "run_id": result.get("run_id"),
            "route": result.get("route"),
            "message_length": len(message),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": (
                round((ended_at - started_at) * 1000)
                if started_at
                else None
            ),
            "stop_reason": result.get("stop_reason"),
            "iteration_count": result.get("iteration_count"),
            "tool_call_count": len(tool_calls),
            "tool_calls": [
                {"name": call["name"], "status": call["status"]}
                for call in tool_calls
            ],
            "supervisor_rounds": result.get("supervisor_rounds") or None,
            "injection_flags": injection_flags or [],
        },
    )


def log_run_failed(
    exc: Exception,
    user_id: str,
    run_id: str,
    step: str,
    started_at: float,
) -> None:
    """Log a failed run once, with the step that failed.

    The step is the graph node the error came from (e.g. ``llm``), or the
    service step outside the graph (e.g. ``save_history``). The run ID and
    step are also attached to the exception so app-level handlers can
    include them without logging the traceback a second time.
    """
    step = getattr(exc, AGENT_STEP_ATTR, None) or step

    logger.error(
        "Agent execution failed",
        extra={
            **get_log_context(),
            "user_id": user_id,
            "run_id": run_id,
            "step": step,
            "error_type": type(exc).__name__,
            "duration_ms": round((time.time() - started_at) * 1000),
        },
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    mark_error_logged(exc, run_id=run_id, step=step)


def run_response(result: dict, run_id: str, actions: list[dict]) -> dict:
    awaiting = bool(actions)

    return {
        "response": (
            approval_message(run_id, actions)
            if awaiting
            else result["messages"][-1].content
        ),
        "sources": result.get("sources", []),
        "run_id": run_id,
        "conversation_id": result.get("conversation_id"),
        "route": result.get("route") or None,
        "status": STATUS_AWAITING_APPROVAL if awaiting else STATUS_COMPLETED,
        "approval": actions or None,
    }


async def _finish_run(
    graph,
    result: dict,
    user_id: str,
    run_id: str,
    message: str,
    model: str,
    injection_flags: list[str],
) -> dict:
    """Shared tail of a new or resumed run: pause, or save and complete.

    History is only saved once the run completes, so a run waiting for
    approval leaves no half-finished turn in `chat_history`.
    """
    actions = await pending_approvals(graph, run_id)
    response = run_response(result, run_id, actions)

    if actions:
        log_run_awaiting_approval(user_id, result, actions)
        return response

    await save_chat_history(
        user_id=user_id,
        message=message,
        response=response["response"],
        model=model,
        conversation_id=response["conversation_id"],
    )

    log_run_completed(user_id, message, result, injection_flags)

    return response


async def generate_agent_response(
    user_id: str,
    message: str,
    model: str,
    role: str = ROLE_USER,
    conversation_id: str | None = None,
) -> dict:
    """Answer one message.

    With a conversation ID, context comes from that conversation only.
    Without one, a new conversation is started and context comes from the
    user's recent turns.
    """
    run_id = str(uuid.uuid4())
    started_at = time.time()
    step = STEP_LOAD_HISTORY

    with bind_log_context(run_id=run_id, user_id=user_id):
        try:
            messages = await build_agent_messages(
                user_id=user_id,
                message=message,
                conversation_id=conversation_id,
            )

            initial_state = build_initial_state(
                messages, run_id, started_at, user_id, message,
                conversation_id,
            )

            log_run_started(user_id, message, initial_state, role)
            injection_flags = screen_input(message, "user_message")

            graph = create_run_graph(role)

            step = STEP_GRAPH
            result = await graph.ainvoke(initial_state, run_config(run_id))

            step = STEP_SAVE_HISTORY
            return await _finish_run(
                graph, result, user_id, run_id, message, model,
                injection_flags,
            )
        except Exception as exc:
            log_run_failed(exc, user_id, run_id, step, started_at)
            raise


async def resume_agent_run(
    user_id: str,
    run_id: str,
    approved: bool,
    model: str,
    role: str = ROLE_USER,
) -> dict:
    """Continue a run paused for approval with the user's decision."""
    graph = create_run_graph(role)
    snapshot = await graph.aget_state(run_config(run_id))

    # Another user's run is reported as missing, not forbidden, so run IDs
    # cannot be probed.
    if not snapshot.values or snapshot.values.get("user_id") != user_id:
        raise RunNotFoundError(run_id)

    if not await pending_approvals(graph, run_id):
        raise RunNotPendingError(run_id)

    message = snapshot.values.get("user_message", "")
    started_at = time.time()
    step = STEP_GRAPH

    with bind_log_context(run_id=run_id, user_id=user_id):
        logger.info(
            "Agent execution resumed",
            extra={
                **get_log_context(),
                "user_id": user_id,
                "run_id": run_id,
                "approved": approved,
            },
        )

        try:
            result = await graph.ainvoke(
                Command(resume={"approved": approved}),
                run_config(run_id),
            )

            step = STEP_SAVE_HISTORY
            return await _finish_run(
                graph, result, user_id, run_id, message, model,
                detect_injection(message),
            )
        except Exception as exc:
            log_run_failed(exc, user_id, run_id, step, started_at)
            raise


async def stream_agent_response(
    user_id: str,
    message: str,
    role: str = ROLE_USER,
    run_id: str | None = None,
    outcome: dict | None = None,
    conversation_id: str | None = None,
):
    """Stream the final answer's tokens.

    Only LLM calls tagged as final answers are forwarded, never the
    classifier, supervisor decisions, or worker agents. If the run pauses
    for approval, the stream ends with a note on how to approve it, and
    `outcome` (if given) is filled with the run's status and pending actions
    so the caller knows not to save the turn yet. `outcome` also carries the
    conversation the turn belongs to (a new one when none was given).
    """
    run_id = run_id or str(uuid.uuid4())
    started_at = time.time()
    step = STEP_LOAD_HISTORY
    outcome = outcome if outcome is not None else {}
    outcome.update(
        run_id=run_id,
        status=None,
        approval=None,
        conversation_id=conversation_id or str(uuid.uuid4()),
    )

    with bind_log_context(run_id=run_id, user_id=user_id):
        try:
            messages = await build_agent_messages(
                user_id=user_id,
                message=message,
                conversation_id=conversation_id,
            )

            initial_state = build_initial_state(
                messages, run_id, started_at, user_id, message,
                outcome["conversation_id"],
            )

            log_run_started(user_id, message, initial_state, role)
            injection_flags = screen_input(message, "user_message")

            graph = create_run_graph(role)

            final_state = initial_state
            streamed_text = False
            step = STEP_GRAPH

            async for namespace, mode, payload in graph.astream(
                initial_state,
                run_config(run_id),
                stream_mode=["messages", "values"],
                subgraphs=True,
            ):
                if mode == "values":
                    if not namespace:
                        final_state = payload
                    continue

                message_chunk, metadata = payload

                if FINAL_ANSWER_TAG not in (metadata.get("tags") or ()):
                    continue

                if not isinstance(message_chunk, AIMessageChunk):
                    continue

                if (
                    message_chunk.content
                    and isinstance(message_chunk.content, str)
                ):
                    streamed_text = True
                    yield message_chunk.content

            actions = await pending_approvals(graph, run_id)
        except Exception as exc:
            # A client disconnect is GeneratorExit, not a failure.
            log_run_failed(exc, user_id, run_id, step, started_at)
            raise

        outcome["route"] = final_state.get("route") or None

        if actions:
            outcome.update(status=STATUS_AWAITING_APPROVAL, approval=actions)
            log_run_awaiting_approval(user_id, final_state, actions)
            separator = "\n\n" if streamed_text else ""
            yield separator + approval_message(run_id, actions)
            return

        outcome["status"] = STATUS_COMPLETED
        log_run_completed(user_id, message, final_state, injection_flags)
