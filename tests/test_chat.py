from unittest.mock import patch

class FakeStreamingChain:
    async def astream(self, inputs):
        yield "Hello "
        yield "from "
        yield "streaming!"

def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_chat_mock_response(client, auth_headers):
    response = client.post(
        "/api/chat/chat",
        json={
            "message": "Hello",
            "temperature": 0.7,
            "max_tokens": 100,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Mock response: Hello"


def test_chat_empty_message(client, auth_headers):
    response = client.post(
        "/api/chat/chat",
        json={
            "message": "",
            "temperature": 0.7,
            "max_tokens": 100,
        },
        headers=auth_headers,
    )

    assert response.status_code == 422

def test_chat_stream_mock_response(client, auth_headers):
    response = client.post(
        "/api/chat/chat/stream",
        json={
            "message": "Hello",
            "temperature": 0.7,
            "max_tokens": 100,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.text == "Mock response: Hello"

def test_chat_stream_saves_history(client, auth_headers):
    response = client.post(
        "/api/chat/chat/stream",
        json={
            "message": "Hello streaming",
            "temperature": 0.7,
            "max_tokens": 100,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.text == "Mock response: Hello streaming"

    history_response = client.get(
        "/api/chat/history",
        headers=auth_headers,
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert history["count"] == 1
    assert len(history["history"]) == 1

    assert history["history"][0]["message"] == "Hello streaming"
    assert history["history"][0]["response"] == "Mock response: Hello streaming"

def test_chat_stream_unauthorized(client):
    response = client.post(
        "/api/chat/chat/stream",
        json={
            "message": "Hello",
            "temperature": 0.7,
            "max_tokens": 100,
        },
    )

    assert response.status_code == 401

def test_chat_stream_with_mocked_llm(client, auth_headers):
    with patch(
        "app.services.chat_service.create_streaming_rag_chain",
        return_value=FakeStreamingChain(),
    ):
        response = client.post(
            "/api/chat/chat/stream",
            json={
                "message": "Test streaming",
                "temperature": 0.7,
                "max_tokens": 100,
            },
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.text == "Hello from streaming!"

    history_response = client.get(
        "/api/chat/history",
        headers=auth_headers,
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert history["count"] == 1
    assert len(history["history"]) == 1

    assert history["history"][0]["message"] == "Test streaming"
    assert history["history"][0]["response"] == "Hello from streaming!"