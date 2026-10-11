from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import ToolMessage

from app.agents import agent_service, orchestrator, router
from app.agents.calculator_agent import SYSTEM_PROMPT
from app.agents.orchestrator import (
    CALC_PROMPT,
    CHAT_PROMPT,
    RAG_PROMPT,
    create_orchestrator_graph,
)
from app.agents.router import RouteDecision, classify_message

QUESTION = {"messages": [("human", "Hello")]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route", "prompt"),
    [
        ("knowledge_base", RAG_PROMPT),
        ("calculation", CALC_PROMPT),
        ("chat", CHAT_PROMPT),
        ("general", SYSTEM_PROMPT),
    ],
)
async def test_each_route_uses_its_agent(scripted_llm, route, prompt):
    scripted_llm.route_to(route).answer("Hi there.")

    result = await create_orchestrator_graph().ainvoke(QUESTION)

    assert result["route"] == route
    assert result["messages"][-1].content == "Hi there."
    assert scripted_llm.calls[0][0].content == prompt


@pytest.mark.asyncio
async def test_route_agent_cannot_call_tools_outside_its_set(scripted_llm):
    scripted_llm.route_to("calculation").call_tool(
        "delete_my_document", document_id="doc-1"
    ).answer("I cannot do that here.")

    result = await create_orchestrator_graph().ainvoke(QUESTION)

    [tool_message] = [
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage)
    ]
    assert tool_message.status == "error"
    assert "not a valid tool" in tool_message.content


def bound_tool_sets(monkeypatch, scripted_llm, role) -> set[tuple[str, ...]]:
    bound = []

    def create_tool_llm(**kwargs):
        bound.append(tuple(sorted(tool.name for tool in kwargs["tools"])))
        return scripted_llm

    monkeypatch.setattr(
        "app.agents.calculator_agent.create_tool_llm",
        create_tool_llm,
    )
    create_orchestrator_graph(role=role)

    return set(bound)


def test_agents_get_only_their_tools(monkeypatch, scripted_llm):
    assert bound_tool_sets(monkeypatch, scripted_llm, "user") == {
        # plain_llm, the coding worker and the supervisor's finalize step
        (),
        ("search_knowledge_base",),
        ("analyze_text", "calculator"),
        (
            "analyze_text",
            "calculator",
            "delete_my_document",
            "search_knowledge_base",
        ),
    }


def test_unknown_role_gets_no_tools_on_any_route(monkeypatch, scripted_llm):
    assert bound_tool_sets(monkeypatch, scripted_llm, "guest") == {()}


@pytest.mark.asyncio
async def test_routing_disabled_always_uses_general_agent(
    scripted_llm, monkeypatch
):
    monkeypatch.setattr(orchestrator, "AGENT_ROUTING_ENABLED", False)
    scripted_llm.route_to("chat").answer("Hi.")

    result = await create_orchestrator_graph().ainvoke(QUESTION)

    assert result["route"] == "general"
    assert scripted_llm.calls[0][0].content == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_classifier_failure_falls_back_to_general(monkeypatch):
    class BrokenModel:
        async def ainvoke(self, messages):
            raise TimeoutError("groq timed out")

    monkeypatch.setattr(router, "create_classifier", lambda: BrokenModel())

    decision = await classify_message([("human", "Hello")])

    assert decision.route == "general"


@pytest.mark.asyncio
async def test_classifier_accepts_dict_output(monkeypatch):
    class DictModel:
        async def ainvoke(self, messages):
            return {"route": "calculation", "reason": "arithmetic"}

    monkeypatch.setattr(router, "create_classifier", lambda: DictModel())

    decision = await classify_message([("human", "2 + 2?")])

    assert decision == RouteDecision(route="calculation", reason="arithmetic")


@pytest.mark.asyncio
async def test_invalid_route_falls_back_to_general(monkeypatch):
    class BadModel:
        async def ainvoke(self, messages):
            return {"route": "weather"}

    monkeypatch.setattr(router, "create_classifier", lambda: BadModel())

    decision = await classify_message([("human", "Rain?")])

    assert decision.route == "general"


LIVE_CASES = [
    ("What is 1234 * 5678?", {"calculation"}),
    ("Hi! How are you today?", {"chat"}),
    (
        "According to our docs, how do I configure hybrid search?",
        {"knowledge_base"},
    ),
    ("Delete my document doc-123.", {"general"}),
    (
        "Look up the documented API rate limit, compute the requests per "
        "day it allows, and write a Python snippet that enforces it.",
        {"multi_agent"},
    ),
]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_classifier_routes_typical_messages():
    decisions = [
        await classify_message([("human", message)])
        for message, _ in LIVE_CASES
    ]

    for (message, expected), decision in zip(LIVE_CASES, decisions):
        print(f"\n{decision.route:15} {message} ({decision.reason})")

    correct = sum(
        decision.route in expected
        for (_, expected), decision in zip(LIVE_CASES, decisions)
    )

    # An LLM classifier may miss an edge case; a regression misses several.
    assert correct >= len(LIVE_CASES) - 1


@pytest.mark.asyncio
async def test_response_and_completion_log_include_route(
    scripted_llm, monkeypatch, caplog
):
    monkeypatch.setattr(
        agent_service, "get_recent_chat_history", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(agent_service, "save_chat_history", AsyncMock())
    scripted_llm.route_to("chat").answer("Hello!")

    with caplog.at_level("INFO"):
        response = await agent_service.generate_agent_response(
            user_id="user-1", message="Hi", model="test-model"
        )

    [completed] = [
        record
        for record in caplog.records
        if record.message == "Agent execution completed"
    ]

    assert response["route"] == "chat"
    assert response["status"] == "completed"
    assert response["approval"] is None
    assert completed.route == "chat"
