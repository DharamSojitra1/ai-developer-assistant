import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app.agents import agent_service
from app.agents.agent_service import generate_agent_response, stream_agent_response
from app.exceptions import unhandled_exception_handler
from app.middleware import RequestIdMiddleware
from app.utils.log_context import logged_error_context

AGENT_CHAT = {"message": "What is 25 * 4?"}


def records(caplog, message: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.message == message]


def request_completed(caplog, path: str) -> logging.LogRecord:
    [record] = [
        record
        for record in records(caplog, "Request completed")
        if record.path == path
    ]
    return record


@pytest.fixture
def caplog_info(caplog):
    caplog.set_level(logging.INFO)
    return caplog


@pytest.fixture
def no_history(monkeypatch):
    monkeypatch.setattr(
        agent_service,
        "get_recent_chat_history",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(agent_service, "save_chat_history", AsyncMock())


def database_down(*args, **kwargs):
    raise ServerSelectionTimeoutError("127.0.0.1:1: connection refused")


# --------------------------------------------------------- request latency


def test_every_request_is_logged_with_latency(client, caplog_info):
    response = client.get("/health", headers={"X-Request-ID": "req-health"})

    record = request_completed(caplog_info, "/health")

    assert response.status_code == 200
    assert record.request_id == "req-health"
    assert record.method == "GET"
    assert record.route == "/health"
    assert record.status_code == 200
    assert record.duration_ms >= 0
    assert record.llm_calls == 0
    assert record.total_tokens == 0
    assert record.user_id is None


def test_request_log_uses_route_template_and_error_status(client, caplog_info):
    client.delete("/api/rag/documents/doc-123")

    record = request_completed(caplog_info, "/api/rag/documents/doc-123")

    assert record.route == "/api/rag/documents/{document_id}"
    assert record.status_code in (401, 403)


def test_unhandled_error_request_is_logged_as_500(caplog_info):
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")

    record = request_completed(caplog_info, "/boom")

    assert response.status_code == 500
    assert record.status_code == 500
    assert record.levelno == logging.WARNING


# ----------------------------------------------------- token usage per user


def test_agent_request_aggregates_tokens_per_request_and_user(
    client,
    auth_headers,
    scripted_llm,
    caplog_info,
):
    scripted_llm.usage = (100, 20)
    scripted_llm.call_tool("calculator", expression="25 * 4").answer("100")

    response = client.post("/api/agent/chat", json=AGENT_CHAT, headers=auth_headers)

    record = request_completed(caplog_info, "/api/agent/chat")

    assert response.status_code == 200
    assert record.user_id
    assert record.llm_calls == 2
    assert record.input_tokens == 200
    assert record.output_tokens == 40
    assert record.total_tokens == 240

    # Every log written during the request is attributed to the user.
    llm_records = records(caplog_info, "LLM call completed")
    assert {r.user_id for r in llm_records} == {record.user_id}

    usage = client.get("/api/usage/me", headers=auth_headers).json()

    assert usage["days"] == 30
    assert usage["totals"] == {
        "requests": 1,
        "llm_calls": 2,
        "input_tokens": 200,
        "output_tokens": 40,
        "total_tokens": 240,
    }
    assert len(usage["daily"]) == 1


def test_streamed_request_is_measured_until_the_body_ends(
    client,
    auth_headers,
    scripted_llm,
    caplog_info,
):
    scripted_llm.usage = (50, 10)
    scripted_llm.answer("Streaming answer here.")

    response = client.post(
        "/api/agent/chat/stream",
        json=AGENT_CHAT,
        headers=auth_headers,
    )

    record = request_completed(caplog_info, "/api/agent/chat/stream")

    assert response.text == "Streaming answer here."
    assert record.llm_calls == 1
    assert record.total_tokens == 60

    # The request is only complete after the run (inside the body) is.
    order = [r.message for r in caplog_info.records]
    assert order.index("Agent execution completed") < order.index(
        "Request completed",
        order.index("Agent execution completed"),
    )


def test_usage_accumulates_across_requests(client, auth_headers, scripted_llm):
    scripted_llm.usage = (10, 5)
    scripted_llm.answer("one").answer("two")

    for _ in range(2):
        client.post("/api/agent/chat", json=AGENT_CHAT, headers=auth_headers)

    totals = client.get("/api/usage/me", headers=auth_headers).json()["totals"]

    assert totals["requests"] == 2
    assert totals["total_tokens"] == 30


def test_usage_is_per_user(client, auth_headers, admin_token, scripted_llm):
    scripted_llm.usage = (10, 5)
    scripted_llm.answer("hi")

    client.post("/api/agent/chat", json=AGENT_CHAT, headers=auth_headers)

    admin_usage = client.get(
        "/api/usage/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    assert admin_usage["totals"]["total_tokens"] == 0
    assert admin_usage["daily"] == []


def test_requests_without_llm_calls_are_not_recorded(client, auth_headers):
    client.get("/api/chat/history", headers=auth_headers)

    usage = client.get("/api/usage/me", headers=auth_headers).json()

    assert usage["daily"] == []


def test_usage_requires_authentication(client):
    assert client.get("/api/usage/me").status_code in (401, 403)


def test_failed_usage_recording_does_not_fail_the_request(
    client,
    auth_headers,
    scripted_llm,
    caplog_info,
):
    scripted_llm.usage = (10, 5)
    scripted_llm.answer("hi")

    with patch("app.middleware.record_token_usage", side_effect=database_down):
        response = client.post(
            "/api/agent/chat",
            json=AGENT_CHAT,
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert records(caplog_info, "Failed to record token usage")


# ---------------------------------------------------- error run ID and step


@pytest.mark.asyncio
async def test_llm_failure_is_logged_with_run_id_and_graph_step(
    caplog_info,
    scripted_llm,
    no_history,
):
    # An empty script makes the LLM node raise.
    with pytest.raises(AssertionError) as exc_info:
        await generate_agent_response(user_id="u-1", message="hi", model="m")

    [record] = records(caplog_info, "Agent execution failed")
    [started] = records(caplog_info, "Agent execution started")

    assert record.levelno == logging.ERROR
    assert record.step == "llm"
    assert record.run_id == started.run_id
    assert record.user_id == "u-1"
    assert record.error_type == "AssertionError"
    assert record.exc_info is not None
    assert logged_error_context(exc_info.value)["step"] == "llm"


@pytest.mark.parametrize(
    "failing, step",
    [
        ("get_recent_chat_history", "load_history"),
        ("save_chat_history", "save_history"),
    ],
)
@pytest.mark.asyncio
async def test_failure_outside_the_graph_reports_service_step(
    caplog_info,
    scripted_llm,
    no_history,
    monkeypatch,
    failing,
    step,
):
    scripted_llm.answer("hi")
    monkeypatch.setattr(agent_service, failing, AsyncMock(side_effect=database_down))

    with pytest.raises(ServerSelectionTimeoutError):
        await generate_agent_response(user_id="u-1", message="hi", model="m")

    [record] = records(caplog_info, "Agent execution failed")

    assert record.step == step
    assert record.run_id


@pytest.mark.asyncio
async def test_streaming_failure_is_logged_with_step(
    caplog_info,
    scripted_llm,
    no_history,
):
    with pytest.raises(AssertionError):
        async for _ in stream_agent_response(user_id="u-1", message="hi"):
            pass

    [record] = records(caplog_info, "Agent execution failed")

    assert record.step == "llm"
    assert record.run_id


def test_api_error_log_includes_run_id_and_step_without_second_traceback(
    client,
    auth_headers,
    caplog_info,
):
    with patch(
        "app.agents.agent_service.get_recent_chat_history",
        side_effect=database_down,
    ):
        response = client.post(
            "/api/agent/chat",
            json=AGENT_CHAT,
            headers=auth_headers,
        )

    [agent_record] = records(caplog_info, "Agent execution failed")
    [handler_record] = records(caplog_info, "Database unavailable")

    assert response.status_code == 503
    assert handler_record.run_id == agent_record.run_id
    assert handler_record.step == "load_history"
    assert handler_record.request_id == response.headers["X-Request-ID"]
    assert handler_record.path == "/api/agent/chat"
    assert handler_record.user_id == agent_record.user_id
    assert handler_record.exc_info is None
