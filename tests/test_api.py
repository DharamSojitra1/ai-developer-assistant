
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_chat_with_valid_api_key(client, auth_headers):
    response = client.post(
        "/api/chat/chat",
        headers=auth_headers,
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


def test_chat_with_invalid_api_key(client):
    response = client.post(
        "/api/chat/chat",
        headers={"X-API-Key": "wrong-api-key"},
        json={
            "message": "Hello",
            "temperature": 0.7,
            "max_tokens": 1024,
        },
    )

    assert response.status_code == 401