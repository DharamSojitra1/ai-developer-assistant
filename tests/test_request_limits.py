import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.config import CHAT_MAX_MESSAGE_CHARS, MAX_REQUEST_BYTES
from app.middleware import BodySizeLimitMiddleware
from app.schemas import MAX_RESPONSE_TOKENS


@pytest.fixture
def small_app() -> TestClient:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=100)

    @app.post("/echo")
    async def echo(request: Request):
        return {"size": len(await request.body())}

    return TestClient(app)


def test_body_within_limit_passes(small_app):
    response = small_app.post("/echo", content=b"x" * 100)

    assert response.status_code == 200
    assert response.json() == {"size": 100}


def test_declared_oversized_body_is_rejected(small_app):
    response = small_app.post("/echo", content=b"x" * 101)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_chunked_oversized_body_is_rejected(small_app):
    def chunks():
        for _ in range(5):
            yield b"x" * 30

    response = small_app.post("/echo", content=chunks())

    assert response.status_code == 413


def test_app_rejects_oversized_body(client, auth_headers):
    huge = "x" * (MAX_REQUEST_BYTES + 1)
    response = client.post(
        "/api/chat/chat",
        content=huge,
        headers={**auth_headers, "Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_message_over_max_length_is_rejected(client, auth_headers):
    response = client.post(
        "/api/agent/chat",
        json={"message": "x" * (CHAT_MAX_MESSAGE_CHARS + 1)},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_max_tokens_is_capped(client, auth_headers):
    response = client.post(
        "/api/chat/chat",
        json={"message": "hi", "max_tokens": MAX_RESPONSE_TOKENS + 1},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_search_query_length_is_capped(client, auth_headers):
    response = client.post(
        "/api/rag/search",
        json={"query": "q" * 501},
        headers=auth_headers,
    )

    assert response.status_code == 422
