"""Run the real agent graph for one evaluation question (paid API calls)."""

from langchain_core.messages import ToolMessage

from app.agents.calculator_agent import SOURCE_TOOLS, create_agent_graph
from app.tools.registry import ROLE_USER
from evals.checks import AgentRunOutcome
from evals.usage import measure_usage


async def run_agent(question: str, role: str = ROLE_USER) -> AgentRunOutcome:
    # Uses the configured agent settings so evaluation measures what users get.
    graph = create_agent_graph(role=role)

    with measure_usage() as measurement:
        result = await graph.ainvoke(
            {
                "messages": [("human", question)],
                "iteration_count": 0,
                "sources": [],
            }
        )

    tools_called = [
        call["name"]
        for message in result["messages"]
        for call in getattr(message, "tool_calls", None) or []
    ]
    sources = result.get("sources", [])

    return AgentRunOutcome(
        answer=result["messages"][-1].content,
        tools_called=tools_called,
        source_ids=[source["document_id"] for source in sources],
        contexts=[source["text"] for source in sources],
        # Knowledge base and web results are already in contexts as plain text.
        tool_outputs=[
            message.content
            for message in result["messages"]
            if isinstance(message, ToolMessage)
            and message.name not in SOURCE_TOOLS
        ],
        usage=measurement.usage,
    )
