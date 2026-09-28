
from app.routes import chat


def test_get_chat_history(client, auth_headers, monkeypatch):
    mock_history = [
        {
            "id": "abc123",
            "message": "Hello",
            "response": "Mock response: Hello",
            "model": "test-model",
            "created_at": "2026-09-28T10:00:00Z",
        }
    ]

    async def mock_get_chat_history(user_id, limit=20, skip=0):
        return mock_history[:limit]

    monkeypatch.setattr(
        chat,
        "get_chat_history",
        mock_get_chat_history,
    )

    response = client.get(
        "/api/chat/history",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1
    assert data["history"][0]["message"] == "Hello"


def test_chat_history_limit_validation(client, auth_headers):
    response = client.get(
        "/api/chat/history?limit=200",
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_chat_history_skip_validation(client, auth_headers):
    response = client.get(
        "/api/chat/history?skip=-1",
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_chat_history_pagination(client, auth_headers, monkeypatch):
    mock_history = [
        {
            "id": str(i),
            "message": f"Message {i}",
            "response": f"Response {i}",
            "model": "test-model",
            "created_at": "2026-09-28T10:00:00Z",
        }
        for i in range(10)
    ]

    async def mock_get_chat_history(user_id, limit=20, skip=0):
        return mock_history[skip:skip + limit]

    monkeypatch.setattr(
        chat,
        "get_chat_history",
        mock_get_chat_history,
    )

    response = client.get(
        "/api/chat/history?limit=3&skip=3",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert response.json()["history"][0]["message"] == "Message 3"