from typing import Annotated, TypedDict
import json
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from app.services.tool_llm_service import create_tool_llm
from app.tools.calculator import calculator
from app.tools.rag_search import search_knowledge_base
from app.tools.text_analyzer import analyze_text
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration_count: int
    sources: list[dict]


MAX_ITERATIONS = 5

SYSTEM_PROMPT = (
    "You are a helpful assistant with tools. "
    "Always use the calculator tool for any arithmetic, "
    "even if you know the answer. "
    "Use the analyze_text tool when asked to analyze text."
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
        ]
    }

def collect_sources(state: AgentState):
    sources = list(state.get("sources", []))

    for message in state["messages"]:
        if not isinstance(message, ToolMessage):
            continue

        if message.name != "search_knowledge_base":
            continue

        try:
            tool_data = json.loads(message.content)

            for result in tool_data.get("results", []):
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

        except (json.JSONDecodeError, TypeError):
            continue

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

def create_agent_graph(
    temperature: float = 0,
    max_tokens: int = 500,
):
    tools = [
        calculator,
        analyze_text,
        search_knowledge_base,
    ]

    llm = create_tool_llm(
        temperature=temperature,
        max_tokens=max_tokens,
    )

    llm_with_tools = llm.bind_tools(tools)

    def call_llm(state: AgentState):
        response = invoke_agent_llm(
            llm_with_tools,
            [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]],
        )

        return {
            "messages": [response],
            "iteration_count": (
                state.get("iteration_count", 0) + 1
            ),
        }

    tool_node = ToolNode(
        tools,
        handle_tool_errors=True,
    )

    builder = StateGraph(AgentState)

    builder.add_node("llm", call_llm)
    builder.add_node("tools", tool_node)
    builder.add_node("collect_sources", collect_sources)
    builder.add_node("max_iterations", max_iterations)

    builder.add_edge(START, "llm")

    builder.add_conditional_edges(
        "llm",
        should_continue,
        {
            "tools": "tools",
            "max_iterations": "max_iterations",
            END: END,
        },
    )

    builder.add_edge("tools", "collect_sources")
    builder.add_edge("collect_sources", "llm")
    builder.add_edge("max_iterations", END)

    return builder.compile()


graph = create_agent_graph()

