import sys
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pymongo import AsyncMongoClient, MongoClient

from app.main import app
from app import database as db
from app.config import MONGODB_URI

sys.stdout.reconfigure(encoding="utf-8")


TEST_DB_NAME = "ai_developer_assistant_test"


@pytest.fixture(scope="session")
def test_db():
    test_database = db.client[TEST_DB_NAME]
    original_database = db.database
    original_lifespan = app.router.lifespan_context

    db.database = test_database

    @asynccontextmanager
    async def test_lifespan(app):
        await db.create_users_index()
        yield

    app.router.lifespan_context = test_lifespan

    try:
        yield test_database
    finally:
        app.router.lifespan_context = original_lifespan
        db.database = original_database

        with MongoClient(MONGODB_URI) as sync_client:
            sync_client.drop_database(TEST_DB_NAME)


@pytest_asyncio.fixture
async def async_test_db(test_db, monkeypatch):
    # AsyncMongoClient is bound to the event loop it is first used on,
    # and pytest-asyncio gives each test its own loop.
    client = AsyncMongoClient(MONGODB_URI)
    monkeypatch.setattr(db, "database", client[TEST_DB_NAME])

    try:
        yield db.database
    finally:
        await client.close()


@pytest.fixture(scope="session")
def app_client(test_db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(app_client, test_db):
    # Reset test data before each test.
    with MongoClient(MONGODB_URI) as sync_client:
        test_database = sync_client[TEST_DB_NAME]

        for collection_name in (
            "users",
            "refresh_tokens",
            "chat_history",
        ):
            test_database[collection_name].delete_many({})

    yield app_client

@pytest.fixture
def auth_headers(client):
    payload = {
        "email": "history-test@example.com",
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

    access_token = login_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {access_token}"
    }