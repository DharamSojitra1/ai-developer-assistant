from unittest.mock import AsyncMock, patch

from pymongo.errors import ServerSelectionTimeoutError

from app.limiter import limiter


CREDENTIALS = {
    "email": "db-down@example.com",
    "password": "StrongPass123!",
}


def assert_database_unavailable(response):
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert body["request_id"]

    # Connection details must not leak to clients.
    assert "127.0.0.1" not in response.text
    assert "ServerSelection" not in response.text


def server_selection_timeout(*args, **kwargs):
    raise ServerSelectionTimeoutError("127.0.0.1:1: connection refused")


def test_register_returns_503_when_database_is_down(mongo_down):
    response = mongo_down.post("/api/auth/register", json=CREDENTIALS)

    assert_database_unavailable(response)


def test_login_returns_503_when_database_is_down(mongo_down):
    response = mongo_down.post("/api/auth/login", json=CREDENTIALS)

    assert_database_unavailable(response)


def test_authenticated_request_returns_503_when_database_is_down(
    auth_headers,
    mongo_down,
):
    # The token is valid, but looking up the user needs the database.
    response = mongo_down.get("/api/chat/history", headers=auth_headers)

    assert_database_unavailable(response)


def test_health_check_still_works_when_database_is_down(mongo_down):
    response = mongo_down.get("/health")

    assert response.status_code == 200


def test_agent_chat_returns_503_when_history_cannot_load(
    client,
    auth_headers,
):
    with patch(
        "app.agents.agent_service.get_recent_chat_history",
        side_effect=server_selection_timeout,
    ):
        response = client.post(
            "/api/agent/chat",
            json={"message": "What is 2 + 2?"},
            headers=auth_headers,
        )

    assert_database_unavailable(response)


def test_chat_returns_503_not_ai_error_when_history_cannot_save(
    client,
    auth_headers,
):
    limiter.reset()

    with (
        patch(
            "app.routes.chat.generate_response",
            new_callable=AsyncMock,
            return_value={"response": "Hi", "sources": []},
        ),
        patch(
            "app.routes.chat.save_chat_history",
            side_effect=server_selection_timeout,
        ),
    ):
        response = client.post(
            "/api/chat/chat",
            json={"message": "Hello"},
            headers=auth_headers,
        )

    assert_database_unavailable(response)
