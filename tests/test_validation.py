
import pytest


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
def test_invalid_chat_input(client, auth_headers, payload):
    response = client.post(
        "/api/chat/chat",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 422


def test_missing_message(client, auth_headers):
    response = client.post(
        "/api/chat/chat",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 422