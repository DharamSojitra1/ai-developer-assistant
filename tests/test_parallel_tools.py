import asyncio
import time

import pytest
from langchain_core.tools import tool

from app.agents import calculator_agent
from app.agents.calculator_agent import build_tool_agent
from app.tools.calculator import calculator

DELAY = 0.4


@tool
async def slow_lookup(topic: str) -> str:
    """Slow lookup used to check that tool calls overlap."""
    await asyncio.sleep(DELAY)
    return f"notes on {topic}"


@tool
async def slow_count(text: str) -> str:
    """Slow word count used to check that tool calls overlap."""
    await asyncio.sleep(DELAY)
    return str(len(text.split()))


@pytest.mark.asyncio
async def test_tool_calls_from_one_step_run_concurrently(scripted_llm):
    scripted_llm.call_tools(
        ("slow_lookup", {"topic": "auth"}),
        ("slow_count", {"text": "one two three"}),
    ).answer("Both done.")

    graph = build_tool_agent([slow_lookup, slow_count])

    started = time.perf_counter()
    result = await graph.ainvoke({"messages": [("human", "Do both")]})
    elapsed = time.perf_counter() - started

    assert elapsed < DELAY * 1.75
    assert result["messages"][-1].content == "Both done."
    assert result["tool_calls"] == [
        {"name": "slow_lookup", "args": {"topic": "auth"}, "status": "success"},
        {"name": "slow_count", "args": {"text": "one two three"}, "status": "success"},
    ]


@pytest.mark.asyncio
async def test_one_failing_parallel_call_does_not_stop_the_other(scripted_llm):
    scripted_llm.call_tools(
        ("calculator", {"expression": "6 * 7"}),
        ("calculator", {"expression": "1 / 0"}),
    ).answer("One worked.")

    result = await build_tool_agent([calculator]).ainvoke(
        {"messages": [("human", "Two sums")]}
    )

    assert [call["status"] for call in result["tool_calls"]] == [
        "success",
        "error",
    ]


def test_tools_are_bound_with_parallel_tool_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        calculator_agent,
        "create_tool_llm",
        lambda **kwargs: calls.append(kwargs) or _Configurable(),
    )

    calculator_agent.create_agent_llm([calculator], 0, 100)
    calculator_agent.create_agent_llm([], 0, 100)

    assert calls[0]["parallel_tool_calls"] is True
    assert "parallel_tool_calls" not in calls[1]


def test_parallel_tool_calls_can_be_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(calculator_agent, "AGENT_PARALLEL_TOOL_CALLS", False)
    monkeypatch.setattr(
        calculator_agent,
        "create_tool_llm",
        lambda **kwargs: calls.append(kwargs) or _Configurable(),
    )

    calculator_agent.create_agent_llm([calculator], 0, 100)

    assert "parallel_tool_calls" not in calls[0]


class _Configurable:
    def with_config(self, **kwargs):
        return self
