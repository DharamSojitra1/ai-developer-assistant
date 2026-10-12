from collections.abc import Sequence
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import (
    AGENT_MAX_ITERATIONS,
    AGENT_MAX_TOKENS,
    AGENT_PARALLEL_TOOL_CALLS,
    AGENT_TEMPERATURE,
)
from app.agents.prompts import with_security_rules
from app.services.tool_llm_service import create_tool_llm
from app.tools.registry import (
    ROLE_USER,
    approval_describers,
    get_tools_for_role,
)
from app.tools.tool_result import handle_tool_exception, parse_tool_result

# LLM calls tagged with this produce text meant for the user; streaming
# forwards only these tokens (not classifier, supervisor, or worker output).
FINAL_ANSWER_TAG = "agent:final_answer"
WORKER_TAG = "agent:worker"


def _merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    iteration_count: int
    sources: list[dict]
    tool_calls: list[dict]
    run_id: str
    started_at: float
    stop_reason: str
    user_id: str
    user_message: str
    # Where the finished turn is saved, including after an approval resume.
    conversation_id: str
    # Orchestrator route chosen by the classifier.
    route: str
    # Human-in-the-loop decisions, by tool call ID.
    approvals: Annotated[dict, _merge_dicts]
    # Supervisor bookkeeping.
    findings: list[dict]
    supervisor_rounds: int
    next_worker: str
    worker_task: str


MAX_ITERATIONS = AGENT_MAX_ITERATIONS

SYSTEM_PROMPT = with_security_rules(
    "You are a helpful assistant with tools. "
    "Always use the calculator tool for any arithmetic, "
    "even if you know the answer. "
    "Use the analyze_text tool when asked to analyze text. "
    "When a question is about the knowledge base or the application's "
    "documents, call search_knowledge_base and answer only from its "
    "results: do not add facts, examples, or details that the results "
    "do not contain, even if you know them. If the results are empty or "
    "do not answer the question, say the knowledge base does not have "
    "enough information to answer it. "
    "When several independent lookups or calculations are needed, request "
    "all of them in the same step so they run in parallel. "
    "Only call delete_my_document when the user explicitly asks to delete "
    "one of their documents; the user is asked to approve it first."
)


def should_continue(state: AgentState):
    last_message = state["messages"][-1]

    if not last_message.tool_calls:
        return END

    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "max_iterations"

    return "tools"


def max_iterations(state: AgentState):
    return {
        "messages": [
            AIMessage(
                content=(
                    "I stopped because the maximum number "
                    "of agent steps was reached."
                )
            )
        ],
        "stop_reason": "max_iterations",
    }

def collect_tool_calls(state: AgentState):
    requested_args = {}

    for message in state["messages"]:
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                requested_args[call["id"]] = call["args"]

    tool_calls = []

    for message in state["messages"]:
        if not isinstance(message, ToolMessage):
            continue

        payload = parse_tool_result(message.content)

        failed = (
            getattr(message, "status", "success") == "error"
            or (payload is not None and not payload["ok"])
        )

        tool_calls.append(
            {
                "name": message.name,
                "args": requested_args.get(message.tool_call_id, {}),
                "status": "error" if failed else "success",
            }
        )

    return {"tool_calls": tool_calls}

def collect_sources(state: AgentState):
    sources = list(state.get("sources", []))

    for message in state["messages"]:
        if not isinstance(message, ToolMessage):
            continue

        if message.name != "search_knowledge_base":
            continue

        payload = parse_tool_result(message.content)

        if payload is None or not payload["ok"]:
            continue

        for result in (payload["result"] or {}).get("results", []):
            source_key = (
                result.get("document_id"),
                result.get("text"),
            )

            existing_keys = {
                (
                    source.get("document_id"),
                    source.get("text"),
                )
                for source in sources
            }

            if source_key not in existing_keys:
                sources.append(result)

    return {"sources": sources}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(
        (
            TimeoutError,
            ConnectionError,
        )
    ),
    reraise=True,
)
def invoke_agent_llm(llm,messages):
    return llm.invoke(messages)


def create_agent_llm(
    tools: Sequence[BaseTool],
    temperature: float,
    max_tokens: int,
    final_answer: bool = True,
):
    bind_kwargs = (
        {"parallel_tool_calls": True}
        if tools and AGENT_PARALLEL_TOOL_CALLS
        else {}
    )

    llm = create_tool_llm(
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        **bind_kwargs,
    )

    return llm.with_config(
        tags=[FINAL_ANSWER_TAG if final_answer else WORKER_TAG]
    )


def make_approval_node(describers: dict):
    """Pause the run for the user's decision before sensitive tool calls.

    The interrupt lives in this node rather than in the tool, so other
    tool calls from the same step are not re-executed when the run resumes.
    The decision is stored per tool call ID; the sensitive tool itself
    refuses to act without an approval recorded for its own call.
    """

    async def request_approval(state: AgentState):
        approvals = state.get("approvals") or {}
        pending = [
            call
            for call in state["messages"][-1].tool_calls
            if call["name"] in describers and call["id"] not in approvals
        ]

        if not pending:
            return {}

        actions = [
            {
                "tool_call_id": call["id"],
                **await describers[call["name"]](call["args"]),
            }
            for call in pending
        ]

        decision = interrupt({"type": "approval_required", "actions": actions})
        approved = isinstance(decision, dict) and decision.get("approved") is True

        return {"approvals": {call["id"]: approved for call in pending}}

    return request_approval


def build_tool_agent(
    tools: Sequence[BaseTool],
    system_prompt: str = SYSTEM_PROMPT,
    temperature: float = AGENT_TEMPERATURE,
    max_tokens: int = AGENT_MAX_TOKENS,
    final_answer: bool = True,
    checkpointer=None,
):
    """ReAct-style tool loop: llm -> (approval) -> tools -> llm.

    Used on its own, as an orchestrator route, and as a supervisor worker.
    """
    tools = list(tools)
    describers = approval_describers(tools)

    llm = create_agent_llm(
        tools,
        temperature=temperature,
        max_tokens=max_tokens,
        final_answer=final_answer,
    )

    def call_llm(state: AgentState):
        response = invoke_agent_llm(
            llm,
            [SystemMessage(content=system_prompt), *state["messages"]],
        )

        update = {
            "messages": [response],
            "iteration_count": (
                state.get("iteration_count", 0) + 1
            ),
        }

        if not response.tool_calls:
            update["stop_reason"] = "final_answer"

        return update

    builder = StateGraph(AgentState)

    builder.add_node("llm", call_llm)
    builder.add_node(
        "tools",
        ToolNode(tools, handle_tool_errors=handle_tool_exception),
    )
    builder.add_node("collect_sources", collect_sources)
    builder.add_node("collect_tool_calls", collect_tool_calls)
    builder.add_node("max_iterations", max_iterations)

    builder.add_edge(START, "llm")

    if describers:
        builder.add_node("approval", make_approval_node(describers))
        builder.add_edge("approval", "tools")

    builder.add_conditional_edges(
        "llm",
        should_continue,
        {
            "tools": "approval" if describers else "tools",
            "max_iterations": "max_iterations",
            END: END,
        },
    )

    builder.add_edge("tools", "collect_sources")
    builder.add_edge("collect_sources", "collect_tool_calls")
    builder.add_edge("collect_tool_calls", "llm")
    builder.add_edge("max_iterations", END)

    return builder.compile(checkpointer=checkpointer)


def create_agent_graph(
    temperature: float = AGENT_TEMPERATURE,
    max_tokens: int = AGENT_MAX_TOKENS,
    role: str = ROLE_USER,
    checkpointer=None,
):
    # The same filtered list is bound to the LLM and given to ToolNode, so a
    # hallucinated call to a tool outside the role is rejected at execution.
    return build_tool_agent(
        get_tools_for_role(role),
        temperature=temperature,
        max_tokens=max_tokens,
        checkpointer=checkpointer,
    )


graph = create_agent_graph()
