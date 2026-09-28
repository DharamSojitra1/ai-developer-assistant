from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_chat_mock_response():
    response = client.post(
        "/chat",
        json={
            "message": "Hello",
            "temperature": 0.7,
            "max_tokens": 100,
        },
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Mock response: Hello"


def test_chat_empty_message():
    response = client.post(
        "/chat",
        json={
            "message": "",
            "temperature": 0.7,
            "max_tokens": 100,
        },
    )

    assert response.status_code == 422