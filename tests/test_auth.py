def test_register_user(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"


def test_register_duplicate_email(client):
    payload = {
        "email": "test@example.com",
        "password": "StrongPass123!",
    }

    client.post("/api/auth/register", json=payload)
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409


def test_login_success(client):
    payload = {
        "email": "test@example.com",
        "password": "StrongPass123!",
    }

    client.post("/api/auth/register", json=payload)

    response = client.post("/api/auth/login", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "StrongPass123!",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401

def test_refresh_token_rotation(client):
    payload = {
        "email": "refresh@example.com",
        "password": "StrongPass123!",
    }

    client.post("/api/auth/register", json=payload)

    login_response = client.post("/api/auth/login", json=payload)
    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != refresh_token

    # The old refresh token must no longer work.
    old_token_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert old_token_response.status_code == 401

def test_logout(client):
    payload = {
        "email": "logout@example.com",
        "password": "StrongPass123!",
    }

    client.post("/api/auth/register", json=payload)

    login_response = client.post("/api/auth/login", json=payload)
    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"

    # Logging out again with the same token should fail.
    second_response = client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
    )

    assert second_response.status_code == 401


def test_protected_route_rejects_invalid_user_id_in_token(client):
    from app.security import create_access_token

    invalid_user_id = "not-a-valid-mongodb-id"
    token = create_access_token(invalid_user_id)

    response = client.post(
        "/api/chat/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Hello"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User no longer exists"


def test_protected_route_rejects_deleted_user(client):
    from app.security import create_access_token

    # A valid ObjectId-shaped ID that does not belong to a user.
    deleted_user_id = "507f1f77bcf86cd799439011"
    token = create_access_token(deleted_user_id)

    response = client.post(
        "/api/chat/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Hello"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User no longer exists"