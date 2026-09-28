import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import API_KEY

client = TestClient(app)

headers = {"X-API-Key": API_KEY}


@pytest.mark.parametrize(
    "payload",
    [
        {"message": ""},
        {"message": "   "},
        {"message": "Hello", "temperature": -0.1},
        {"message": "Hello", "temperature": 1.1},
        {"message": "Hello", "max_tokens": 0},
        {"message": "Hello", "max_tokens": -10},
    ],
)
def test_invalid_chat_input(payload):
    response = client.post(
        "/chat",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422


def test_missing_message():
    response = client.post(
        "/chat",
        headers=headers,
        json={},
    )

    assert response.status_code == 422