from unittest.mock import patch


def test_agent_stream_unauthorized(client):
    response = client.post(
        "/api/agent/chat/stream",
        json={
            "message": "What is 25 * 4?",
            "temperature": 0,
            "max_tokens": 100,
        },
    )

    assert response.status_code in (401, 403)


def test_agent_stream_success(client, auth_headers):
    async def fake_stream_agent_response(
        user_id: str,
        message: str,
    ):
        yield "125 "
        yield "* "
        yield "4 = "
        yield "500"

    with patch(
        "app.routes.agent.stream_agent_response",
        side_effect=fake_stream_agent_response,
    ):
        response = client.post(
            "/api/agent/chat/stream",
            json={
                "message": "What is 125 * 4?",
                "temperature": 0,
                "max_tokens": 100,
            },
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.text == "125 * 4 = 500"

def test_agent_stream_saves_history(client, auth_headers):
    async def fake_stream_agent_response(
        user_id: str,
        message: str,
    ):
        yield "Hello "
        yield "from "
        yield "agent"

    with patch(
        "app.routes.agent.stream_agent_response",
        side_effect=fake_stream_agent_response,
    ):
        response = client.post(
            "/api/agent/chat/stream",
            json={
                "message": "Say hello",
                "temperature": 0,
                "max_tokens": 100,
            },
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.text == "Hello from agent"

    history = client.get(
        "/api/chat/history",
        headers=auth_headers,
    ).json()

    assert history["count"] == 1
    assert history["history"][0]["message"] == "Say hello"
    assert history["history"][0]["response"] == "Hello from agent"