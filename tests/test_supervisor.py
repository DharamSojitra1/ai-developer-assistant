from unittest.mock import AsyncMock

import pytest

from app.agents import agent_service, supervisor
from app.agents.supervisor import (
    FINISH,
    create_supervisor_graph,
    decide_next,
)

REQUEST = "Look up the rate limit, then double it"


def initial_state() -> dict:
    return {
        "messages": [("human", REQUEST)],
        "user_message": REQUEST,
        "findings": [],
        "supervisor_rounds": 0,
        "sources": [],
        "tool_calls": [],
    }


@pytest.mark.asyncio
async def test_workers_run_in_order_and_share_findings(scripted_llm):
    scripted_llm.supervise(
        ("research", "Find the API rate limit"),
        ("analysis", "Double the rate limit"),
    )
    # research worker, analysis worker (tool call, then answer), finalize
    scripted_llm.answer("The limit is 60 requests per minute.")
    scripted_llm.call_tool("calculator", expression="60 * 2").answer("120")
    scripted_llm.answer("Doubled, the limit is 120 requests per minute.")

    result = await create_supervisor_graph().ainvoke(initial_state())

    assert [f["worker"] for f in result["findings"]] == ["research", "analysis"]
    assert result["findings"][1]["result"] == "120"
    assert result["supervisor_rounds"] == 2
    assert result["tool_calls"] == [
        {"name": "calculator", "args": {"expression": "60 * 2"}, "status": "success"}
    ]
    assert result["stop_reason"] == "final_answer"
    assert result["messages"][-1].content == (
        "Doubled, the limit is 120 requests per minute."
    )

    # The analysis worker saw the research finding; finalize saw both.
    analysis_prompt = scripted_llm.calls[1][-1].content
    assert "Double the rate limit" in analysis_prompt
    assert "60 requests per minute" in analysis_prompt

    finalize_prompt = scripted_llm.calls[-1][-1].content
    assert "60 requests per minute" in finalize_prompt
    assert "120" in finalize_prompt


@pytest.mark.asyncio
async def test_workers_have_their_own_message_lists(scripted_llm):
    scripted_llm.supervise(("coding", "Write hello world in Python"))
    scripted_llm.answer("print('hello world')").answer("Here it is.")

    await create_supervisor_graph().ainvoke(initial_state())

    worker_messages = scripted_llm.calls[0]
    # system prompt + the task only; not the user's conversation
    assert len(worker_messages) == 2
    assert worker_messages[-1].content == "Write hello world in Python"


@pytest.mark.asyncio
async def test_max_rounds_guard_forces_finalize(scripted_llm):
    scripted_llm.supervise(*[("coding", f"Attempt {n}") for n in range(10)])
    scripted_llm.answer("v1").answer("v2").answer("Best effort answer.")

    result = await create_supervisor_graph(max_rounds=2).ainvoke(
        initial_state()
    )

    assert result["supervisor_rounds"] == 2
    assert result["stop_reason"] == "supervisor_max_rounds"
    assert result["messages"][-1].content == "Best effort answer."
    assert scripted_llm.remaining == 0


@pytest.mark.asyncio
async def test_decision_failure_finishes(monkeypatch):
    def broken_model(**kwargs):
        raise ConnectionError("groq down")

    monkeypatch.setattr(supervisor, "create_chat_model", broken_model)

    decision = await decide_next(initial_state())

    assert decision.next == FINISH


@pytest.mark.asyncio
async def test_only_final_answer_tokens_stream(scripted_llm, monkeypatch):
    monkeypatch.setattr(
        agent_service, "get_recent_chat_history", AsyncMock(return_value=[])
    )
    scripted_llm.route_to("multi_agent").supervise(
        ("coding", "Write a greeting")
    )
    scripted_llm.answer("worker draft text").answer("Final greeting text")

    outcome = {}
    chunks = [
        chunk
        async for chunk in agent_service.stream_agent_response(
            user_id="user-1",
            message="Write a greeting",
            outcome=outcome,
        )
    ]

    assert "".join(chunks) == "Final greeting text"
    assert outcome["status"] == "completed"
    assert outcome["route"] == "multi_agent"
