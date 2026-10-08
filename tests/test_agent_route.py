from unittest.mock import AsyncMock, patch

def test_agent_chat_unauthorized(client):
    response = client.post(
        "/api/agent/chat",
        json={
            "message": "What is 25 * 4?",
            "temperature": 0,
            "max_tokens": 100,
        },
    )

    assert response.status_code in (401, 403)


def test_agent_chat_success(client, auth_headers):
    with patch(
        "app.routes.agent.generate_agent_response",
        new_callable=AsyncMock,
        return_value={
            "response": "125 * 4 = 500",
            "sources": [],
        },
    ):
        response = client.post(
            "/api/agent/chat",
            json={
                "message": "What is 125 * 4?",
                "temperature": 0,
                "max_tokens": 100,
            },
            headers=auth_headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["response"] == "125 * 4 = 500"
    assert data["sources"] == []


def test_agent_chat_failure(client, auth_headers):
    with patch(
        "app.routes.agent.generate_agent_response",
        new_callable=AsyncMock,
        side_effect=RuntimeError("internal failure"),
    ):
        response = client.post(
            "/api/agent/chat",
            json={
                "message": "Hello",
                "temperature": 0,
                "max_tokens": 100,
            },
            headers=auth_headers,
        )

    assert response.status_code == 500

    data = response.json()

    assert data["detail"] == (
        "Agent failed to process the request."
    )