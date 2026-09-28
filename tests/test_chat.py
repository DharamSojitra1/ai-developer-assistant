
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