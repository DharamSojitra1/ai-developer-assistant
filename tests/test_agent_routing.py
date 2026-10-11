import json
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import ToolMessage

from app.agents.agent_service import stream_agent_response
from app.agents.calculator_agent import create_agent_graph


def tool_messages(result) -> list[ToolMessage]:
    return [m for m in result["messages"] if isinstance(m, ToolMessage)]


@pytest.mark.asyncio
async def test_direct_answer_skips_tools(scripted_llm):
    scripted_llm.answer("Hello there!")

    result = await create_agent_graph().ainvoke(
        {"messages": [("human", "Hi")]}
    )

    assert result["messages"][-1].content == "Hello there!"
    assert tool_messages(result) == []
    assert result["iteration_count"] == 1
    assert scripted_llm.remaining == 0


@pytest.mark.asyncio
async def test_tool_result_is_fed_back_to_llm(scripted_llm):
    scripted_llm.call_tool("calculator", expression="6 * 7").answer(
        "The answer is 42."
    )

    result = await create_agent_graph().ainvoke(
        {"messages": [("human", "What is 6 * 7?")]}
    )

    second_call_messages = scripted_llm.calls[1]
    fed_back = [m for m in second_call_messages if isinstance(m, ToolMessage)]

    assert json.loads(fed_back[-1].content)["result"] == "42"
    assert result["messages"][-1].content == "The answer is 42."
    assert result["tool_calls"] == [
        {
            "name": "calculator",
            "args": {"expression": "6 * 7"},
            "status": "success",
        }
    ]
    assert result["stop_reason"] == "final_answer"


@pytest.mark.asyncio
async def test_multiple_tool_calls_in_one_step(scripted_llm):
    scripted_llm.call_tools(
        ("calculator", {"expression": "2 + 2"}),
        ("analyze_text", {"text": "hello world"}),
    ).answer("Done.")

    result = await create_agent_graph().ainvoke(
        {"messages": [("human", "Do both")]}
    )

    assert {m.name for m in tool_messages(result)} == {
        "calculator",
        "analyze_text",
    }
    assert result["iteration_count"] == 2


@pytest.mark.asyncio
async def test_rag_tool_results_become_sources(scripted_llm):
    source = {"document_id": "gen-ai-basics", "text": "Generative AI..."}
    scripted_llm.call_tool(
        "search_knowledge_base",
        query="What is Generative AI?",
    ).answer("Generative AI creates content.")

    with patch(
        "app.tools.rag_search.rag_service.retrieve",
        new_callable=AsyncMock,
        return_value=[
            {"text": source["text"], "metadata": {"document_id": "gen-ai-basics"}}
        ],
    ):
        result = await create_agent_graph().ainvoke(
            {"messages": [("human", "What is Generative AI?")]}
        )

    assert result["sources"] == [source]


@pytest.mark.asyncio
async def test_stream_does_not_leak_tool_output(scripted_llm, async_test_db):
    scripted_llm.call_tool("calculator", expression="25 * 4").answer(
        "25 times 4 is 100."
    )

    chunks = [
        chunk
        async for chunk in stream_agent_response(
            user_id="stream-routing-test",
            message="What is 25 * 4?",
        )
    ]

    streamed = "".join(chunks)

    assert streamed == "25 times 4 is 100."
    assert '"ok"' not in streamed
