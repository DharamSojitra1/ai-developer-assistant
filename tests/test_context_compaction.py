import json
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents import agent_service
from app.agents.calculator_agent import CUT_SHORT_NOTE, mark_if_cut_short
from app.agents.context import COMPACTED_NOTE, compact_tool_context
from app.agents.prompts import with_security_rules
from app.tools.tool_result import tool_error, tool_success


@pytest.mark.asyncio
async def test_long_earlier_answers_are_shortened_in_history():
    history = [
        {"message": "what's new in FastAPI", "response": "| table |" * 200},
        {"message": "hi", "response": "Hello!"},
    ]

    with patch.object(
        agent_service,
        "get_recent_chat_history",
        AsyncMock(return_value=history),
    ):
        messages = await agent_service.build_agent_messages(
            user_id="u1", message="team india last t20 match?"
        )

    long_answer = messages[1][1]
    assert len(long_answer) <= (
        agent_service.HISTORY_RESPONSE_CHARS
        + len(agent_service.HISTORY_TRUNCATION_MARK)
    )
    assert long_answer.endswith(agent_service.HISTORY_TRUNCATION_MARK)
    assert messages[3] == ("ai", "Hello!")
    assert messages[-1] == ("human", "team india last t20 match?")


def test_prompts_say_to_answer_only_the_latest_message():
    assert "Answer only the user's latest message" in with_security_rules("x")


def test_answers_cut_at_the_length_limit_say_so():
    cut = AIMessage(
        content="FastAPI added", response_metadata={"finish_reason": "length"}
    )
    finished = AIMessage(
        content="Done.", response_metadata={"finish_reason": "stop"}
    )

    assert mark_if_cut_short(cut).content == "FastAPI added" + CUT_SHORT_NOTE
    assert mark_if_cut_short(finished).content == "Done."


def search_step(index: int, text_chars: int = 1000, name: str = "web_search"):
    """An AI tool call plus its search result of roughly `text_chars`."""
    call_id = f"call-{index}"
    result = tool_success(
        {
            "results": [
                {
                    "document_id": f"https://example.com/{index}",
                    "title": f"Page {index}",
                    "text": "x" * text_chars,
                }
            ]
        }
    )

    return [
        AIMessage(
            content="",
            tool_calls=[{"name": name, "args": {"query": "q"}, "id": call_id}],
        ),
        ToolMessage(content=result, name=name, tool_call_id=call_id),
    ]


def payload(message) -> dict:
    return json.loads(message.content)["result"]


def test_short_conversations_are_unchanged():
    messages = [HumanMessage(content="hi"), *search_step(1)]

    assert compact_tool_context(messages, budget_chars=4000) == messages


def test_latest_results_are_kept_even_over_budget():
    messages = [HumanMessage(content="hi"), *search_step(1, text_chars=10_000)]

    compacted = compact_tool_context(messages, budget_chars=100)

    assert compacted[-1].content == messages[-1].content


def test_older_results_over_budget_become_references():
    messages = [
        HumanMessage(content="hi"),
        *search_step(1),
        *search_step(2),
        *search_step(3),
    ]

    compacted = compact_tool_context(messages, budget_chars=1500)

    oldest, middle, latest = compacted[2], compacted[4], compacted[6]
    assert latest.content == messages[6].content
    assert middle.content == messages[4].content
    assert payload(oldest) == {
        "compacted": True,
        "note": COMPACTED_NOTE,
        "results": [{"document_id": "https://example.com/1", "title": "Page 1"}],
    }
    assert oldest.tool_call_id == "call-1"
    assert oldest.name == "web_search"


def test_everything_older_than_the_first_overflow_is_compacted():
    messages = [
        HumanMessage(content="hi"),
        *search_step(1, text_chars=10),
        *search_step(2, text_chars=5000),
        *search_step(3),
    ]

    compacted = compact_tool_context(messages, budget_chars=1000)

    assert payload(compacted[2])["compacted"] is True
    assert payload(compacted[4])["compacted"] is True


def test_knowledge_base_results_are_compacted_too():
    messages = [
        HumanMessage(content="hi"),
        *search_step(1, name="search_knowledge_base"),
        *search_step(2),
    ]

    compacted = compact_tool_context(messages, budget_chars=10)

    assert payload(compacted[2])["compacted"] is True


def test_other_tools_and_errors_are_left_alone():
    error = tool_error("Web search failed. Try again later.")
    messages = [
        HumanMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "calculator", "args": {}, "id": "c1"},
                {"name": "web_search", "args": {}, "id": "c2"},
            ],
        ),
        ToolMessage(content="x" * 5000, name="calculator", tool_call_id="c1"),
        ToolMessage(content=error, name="web_search", tool_call_id="c2"),
        *search_step(3),
    ]

    compacted = compact_tool_context(messages, budget_chars=10)

    assert compacted[2].content == messages[2].content
    assert compacted[3].content == error


def test_input_messages_are_not_mutated():
    messages = [HumanMessage(content="hi"), *search_step(1), *search_step(2)]
    original = messages[2].content

    compact_tool_context(messages, budget_chars=10)

    assert messages[2].content == original
