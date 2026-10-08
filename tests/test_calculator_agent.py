import re

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.calculator_agent import graph, should_continue


def get_tool_messages(result, tool_name: str) -> list[ToolMessage]:
    return [
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage) and message.name == tool_name
    ]


def normalize_number_text(text: str) -> str:
    # LLMs may format numbers as "6000", "6,000" or with narrow spaces.
    return re.sub(r"[\s,]", "", text)


@pytest.mark.asyncio
async def test_calculator_agent():
    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "What is 125 * 48?"
                )
            ]
        }
    )

    print("\nFINAL MESSAGES:")
    for message in result["messages"]:
        print(
            type(message).__name__,
            "=>",
            message.content,
        )

    final_message = result["messages"][-1]

    assert "6000" in normalize_number_text(final_message.content)


def test_calculator_agent_graph_structure():
    print("\nGRAPH:")
    print(graph.get_graph().draw_ascii())


@pytest.mark.asyncio
async def test_agent_selects_calculator():
    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "What is 125 * 48?"
                )
            ]
        }
    )

    tool_messages = get_tool_messages(result, "calculator")

    assert tool_messages
    assert tool_messages[-1].content == "6000"


@pytest.mark.asyncio
async def test_agent_selects_text_analyzer():
    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "Analyze this text: Generative AI is powerful"
                )
            ]
        }
    )

    tool_messages = get_tool_messages(result, "analyze_text")

    assert tool_messages
    assert "Characters:" in tool_messages[-1].content
    assert "Words:" in tool_messages[-1].content

@pytest.mark.asyncio
async def test_calculator_tool_error():
    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "What is 10 divided by 0?"
                )
            ],
            "iteration_count": 0,
        }
    )

    print("\nERROR TEST:")

    for message in result["messages"]:
        print(
            type(message).__name__,
            "=>",
            message.content,
        )

    tool_messages = get_tool_messages(result, "calculator")

    assert tool_messages
    assert tool_messages[-1].content == "Error: Cannot divide by zero."


def test_agent_stops_at_max_iterations():
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculator",
                        "args": {"expression": "10 + 10"},
                        "id": "test-call",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        "iteration_count": 5,
    }

    assert should_continue(state) == "max_iterations"

@pytest.mark.asyncio
async def test_agent_selects_rag():
    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "According to the knowledge base, what is Generative AI?"
                )
            ],
            "iteration_count": 0,
        }
    )

    tool_messages = get_tool_messages(
        result,
        "search_knowledge_base",
    )

    assert tool_messages

    assert "Generative AI" in tool_messages[-1].content