import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from groq import RateLimitError

from app.agents import agent_service
from app.utils.disconnect import ClientDisconnectedError, run_until_disconnect


class FakeRequest:
    def __init__(self, disconnect_after_polls: int | None = None):
        self.disconnect_after_polls = disconnect_after_polls
        self.polls = 0

    async def is_disconnected(self) -> bool:
        self.polls += 1
        return (
            self.disconnect_after_polls is not None
            and self.polls >= self.disconnect_after_polls
        )


def groq_rate_limit(retry_after: str | None = "7") -> RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(
        429,
        headers=headers,
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat"),
    )
    return RateLimitError("Rate limit reached", response=response, body=None)


@pytest.mark.asyncio
async def test_finished_work_returns_its_result():
    async def work():
        await asyncio.sleep(0.01)
        return "done"

    result = await run_until_disconnect(FakeRequest(), work(), poll_seconds=0.005)

    assert result == "done"


@pytest.mark.asyncio
async def test_work_errors_propagate():
    async def work():
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        await run_until_disconnect(FakeRequest(), work(), poll_seconds=0.005)


@pytest.mark.asyncio
async def test_disconnect_cancels_the_work():
    cancelled = asyncio.Event()

    async def work():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with pytest.raises(ClientDisconnectedError):
        await run_until_disconnect(
            FakeRequest(disconnect_after_polls=2), work(), poll_seconds=0.005
        )

    assert cancelled.is_set()


class HangingGraph:
    """An agent graph whose LLM call never returns."""

    def __init__(self):
        self.started = asyncio.Event()

    async def ainvoke(self, state, config):
        self.started.set()
        await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_cancelled_run_is_logged_and_not_saved(caplog):
    graph = HangingGraph()
    save = AsyncMock()

    with (
        patch.object(
            agent_service,
            "build_agent_messages",
            AsyncMock(return_value=[("human", "hi")]),
        ),
        patch.object(agent_service, "create_run_graph", return_value=graph),
        patch.object(agent_service, "save_chat_history", save),
        caplog.at_level("INFO", logger="agent"),
    ):
        task = asyncio.create_task(
            agent_service.generate_agent_response(
                user_id="u1", message="hi", model="test-model"
            )
        )
        await asyncio.wait_for(graph.started.wait(), timeout=1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    save.assert_not_awaited()

    messages = [record.message for record in caplog.records]
    assert "Agent execution failed" not in messages
    [cancelled] = [
        record
        for record in caplog.records
        if record.message == "Agent execution cancelled"
    ]
    assert cancelled.stop_reason == "cancelled"
    assert cancelled.step == agent_service.STEP_GRAPH
    assert cancelled.user_id == "u1"
    assert cancelled.duration_ms >= 0


def test_disconnected_agent_request_answers_499(client, auth_headers):
    async def disconnected(request, work):
        work.close()
        raise ClientDisconnectedError

    with patch("app.routes.agent.run_until_disconnect", disconnected):
        response = client.post(
            "/api/agent/chat",
            json={"message": "Hello"},
            headers=auth_headers,
        )

    assert response.status_code == 499


def test_model_rate_limit_is_a_503_with_retry_after(client, auth_headers):
    with patch(
        "app.routes.agent.generate_agent_response",
        new_callable=AsyncMock,
        side_effect=groq_rate_limit("7"),
    ):
        response = client.post(
            "/api/agent/chat",
            json={"message": "Hello"},
            headers=auth_headers,
        )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "7"
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "MODEL_RATE_LIMITED"
    assert "7 seconds" in body["error"]["message"]
    assert body["request_id"]


def test_model_rate_limit_without_header_uses_a_default(client, auth_headers):
    with patch(
        "app.routes.agent.generate_agent_response",
        new_callable=AsyncMock,
        side_effect=groq_rate_limit(None),
    ):
        response = client.post(
            "/api/agent/chat",
            json={"message": "Hello"},
            headers=auth_headers,
        )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "10"
