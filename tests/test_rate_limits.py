from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from app.limiter import rate_limit_key
from app.security import create_access_token, create_refresh_token

CHAT = {"message": "Hello"}


def make_request(ip: str, token: str | None = None) -> Request:
    headers = []

    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/chat/chat",
            "headers": headers,
            "client": (ip, 50000),
        }
    )


def test_authenticated_requests_are_keyed_by_user():
    token = create_access_token("user-1")

    assert rate_limit_key(make_request("1.1.1.1", token)) == "user:user-1"


def test_same_user_shares_a_bucket_across_ips():
    token = create_access_token("user-1")

    assert rate_limit_key(make_request("1.1.1.1", token)) == rate_limit_key(
        make_request("2.2.2.2", token)
    )


def test_different_users_on_one_ip_get_separate_buckets():
    first = rate_limit_key(make_request("1.1.1.1", create_access_token("a")))
    second = rate_limit_key(make_request("1.1.1.1", create_access_token("b")))

    assert first != second


@pytest.mark.parametrize(
    "token",
    [None, "not-a-jwt", create_refresh_token("user-1")],
)
def test_anonymous_invalid_or_refresh_tokens_fall_back_to_ip(token):
    assert rate_limit_key(make_request("9.9.9.9", token)) == "ip:9.9.9.9"


def test_chat_is_limited_per_user(client, auth_headers, admin_token):
    responses = [
        client.post("/api/chat/chat", json=CHAT, headers=auth_headers)
        for _ in range(6)
    ]

    assert [r.status_code for r in responses] == [200] * 5 + [429]

    # Another user from the same IP still has their own budget.
    other = client.post(
        "/api/chat/chat",
        json=CHAT,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert other.status_code == 200


def test_agent_routes_are_rate_limited(client, auth_headers):
    reply = {
        "response": "ok",
        "sources": [],
        "run_id": "run-1",
        "route": "chat",
        "status": "completed",
        "approval": None,
    }

    with patch(
        "app.routes.agent.generate_agent_response",
        new=AsyncMock(return_value=reply),
    ):
        statuses = [
            client.post("/api/agent/chat", json=CHAT, headers=auth_headers).status_code
            for _ in range(11)
        ]

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_login_is_limited_per_ip(client):
    credentials = {"email": "nobody@example.com", "password": "WrongPass123!"}

    statuses = [
        client.post("/api/auth/login", json=credentials).status_code
        for _ in range(6)
    ]

    assert statuses == [401] * 5 + [429]
