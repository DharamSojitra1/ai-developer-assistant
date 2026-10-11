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


def test_regular_user_cannot_index_shared_document(client, user_token):
    response = client.post(
        "/api/rag/index",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"text": "Test document for RBAC", "visibility": "shared"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only admins can add shared documents"


def test_regular_user_cannot_delete_shared_document(
    client, user_token, monkeypatch
):
    from app.routes.rag import rag_service

    monkeypatch.setattr(
        rag_service.vector_store,
        "get_document_metadata",
        lambda document_id: {"visibility": "shared", "owner_id": ""},
    )

    def fail_delete(document_id):
        raise AssertionError("shared document must not be deleted")

    monkeypatch.setattr(rag_service.vector_store, "delete", fail_delete)

    response = client.delete(
        "/api/rag/documents/test-document",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot delete this document"

def test_anonymous_user_cannot_search_documents(client):
    response = client.post(
        "/api/rag/search",
        json={"query": "What is Generative AI?"},
    )

    assert response.status_code == 401


def test_anonymous_user_cannot_index_document(client):
    response = client.post(
        "/api/rag/index",
        json={"text": "RBAC test document"},
    )

    assert response.status_code == 401


def test_anonymous_user_cannot_delete_document(client):
    response = client.delete("/api/rag/documents/test-document")

    assert response.status_code == 401

def test_regular_user_can_search_documents(client, user_token, monkeypatch):
    async def mock_retrieve(query, top_k=None, **filters):
        return []

    monkeypatch.setattr(
        "app.routes.rag.rag_service.retrieve",
        mock_retrieve,
    )

    response = client.post(
        "/api/rag/search",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"query": "What is Generative AI?"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == [] 

def test_admin_can_index_document(client, monkeypatch):
    from app.security import create_access_token

    admin_id = "507f1f77bcf86cd799439011"
    token = create_access_token(admin_id)

    async def mock_get_user_by_id(user_id):
        return {"_id": user_id, "role": "admin"}

    async def mock_index_document(text, document_id=None, **metadata):
        return {
            "document_id": document_id or "test-doc",
            "status": "indexed",
            "chunks_indexed": 1,
            "chunks_embedded": 1,
            "source": metadata["source"],
            "doc_type": metadata["doc_type"],
            "visibility": metadata["visibility"],
        }

    monkeypatch.setattr("app.dependencies.get_user_by_id", mock_get_user_by_id)
    monkeypatch.setattr(
        "app.routes.rag.rag_service.index_document",
        mock_index_document,
    )

    response = client.post(
        "/api/rag/index",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "RBAC admin test document", "visibility": "shared"},
    )

    assert response.status_code == 200
    assert response.json()["chunks_indexed"] == 1


def test_admin_can_delete_document(client, monkeypatch):
    from app.security import create_access_token

    admin_id = "507f1f77bcf86cd799439011"
    token = create_access_token(admin_id)

    async def mock_get_user_by_id(user_id):
        return {"_id": user_id, "role": "admin"}

    def mock_delete_document(document_id, requester=None):
        return {"document_id": document_id, "chunks_deleted": 1}

    monkeypatch.setattr("app.dependencies.get_user_by_id", mock_get_user_by_id)
    monkeypatch.setattr(
        "app.routes.rag.rag_service.delete_document",
        mock_delete_document,
    )

    response = client.delete(
        "/api/rag/documents/test-document",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["chunks_deleted"] == 1

def test_index_endpoint_hides_internal_errors(client, admin_token, monkeypatch):
    async def mock_index_document(text, document_id=None, **metadata):
        raise RuntimeError("mongodb://internal-secret/database")

    monkeypatch.setattr(
        "app.routes.rag.rag_service.index_document",
        mock_index_document,
    )

    response = client.post(
        "/api/rag/index",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"text": "Test document"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Document indexing is temporarily unavailable."
    )
    assert "internal-secret" not in response.text

from concurrent.futures import ThreadPoolExecutor


def test_concurrent_refresh_requests_allow_only_one_success(client):
    payload = {
        "email": "concurrent-refresh@example.com",
        "password": "StrongPass123!",
    }

    register_response = client.post(
        "/api/auth/register",
        json=payload,
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json=payload,
    )
    assert login_response.status_code == 200

    refresh_token = login_response.json()["refresh_token"]
    refresh_payload = {"refresh_token": refresh_token}

    def refresh():
        return client.post(
            "/api/auth/refresh",
            json=refresh_payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(refresh),
            executor.submit(refresh),
        ]
        responses = [future.result() for future in futures]

    statuses = sorted(response.status_code for response in responses)

    assert statuses == [200, 401]       

from datetime import datetime, timedelta, timezone

import jwt

from app.config import JWT_SECRET_KEY, JWT_ALGORITHM


def test_expired_refresh_token_is_rejected(client):
    payload = {
        "email": "expired-refresh@example.com",
        "password": "StrongPass123!",
    }

    client.post("/api/auth/register", json=payload)

    login_response = client.post("/api/auth/login", json=payload)
    assert login_response.status_code == 200

    from app.security import decode_token

    user_id = decode_token(
        login_response.json()["access_token"]
    )["sub"]

    now = datetime.now(timezone.utc)

    expired_token = jwt.encode(
        {
            "sub": user_id,
            "type": "refresh",
            "jti": "expired-refresh-test",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": expired_token},
    )

    assert response.status_code == 401

def test_refresh_endpoint_rejects_access_token(client):
    from app.security import create_access_token

    payload = {
        "email": "wrong-token-type@example.com",
        "password": "StrongPass123!",
    }

    client.post("/api/auth/register", json=payload)
    login_response = client.post("/api/auth/login", json=payload)
    assert login_response.status_code == 200

    from app.security import decode_token

    access_token = login_response.json()["access_token"]
    user_id = decode_token(access_token)["sub"]

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": create_access_token(user_id)},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"

def test_logged_out_refresh_token_cannot_be_reused(client):
    payload = {
        "email": "logout-refresh@example.com",
        "password": "StrongPass123!",
    }

    client.post("/api/auth/register", json=payload)
    login_response = client.post("/api/auth/login", json=payload)
    assert login_response.status_code == 200

    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == 200

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 401