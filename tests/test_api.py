from fastapi.testclient import TestClient

from app.main import app
from app.config import API_KEY

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200


def test_chat_with_valid_api_key(monkeypatch):
    from app.services import chat_service

    monkeypatch.setattr(chat_service, "MOCK_MODE", True)

    response = client.post(
        "/chat",
        headers={"X-API-Key": API_KEY},
        json={
            "message": "Hello",
            "temperature": 0.7,
            "max_tokens": 1024,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "response": "Mock response: Hello"
    }


def test_chat_with_invalid_api_key():
    response = client.post(
        "/chat",
        headers={"X-API-Key": "wrong-api-key"},
        json={
            "message": "Hello",
            "temperature": 0.7,
            "max_tokens": 1024,
        },
    )

    assert response.status_code == 401