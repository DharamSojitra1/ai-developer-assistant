import json
import re
import sys
from collections import deque
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import (
    ChatGeneration,
    ChatGenerationChunk,
    ChatResult,
)
from pydantic import Field
from pymongo import AsyncMongoClient, MongoClient

from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app import database as db
from app.config import MONGODB_URI
from app.services.answerability_service import AnswerabilityResult
from app.services.rag_service import RAGService
from app.services.vector_store_service import VectorStoreService

sys.stdout.reconfigure(encoding="utf-8")


TEST_DB_NAME = "ai_developer_assistant_test"

# Tests using any of these fixtures need a running MongoDB or the app client.
INTEGRATION_FIXTURES = {
    "test_db",
    "async_test_db",
    "app_client",
    "client",
    "auth_headers",
    "user_token",
    "admin_token",
    "mongo_down",
}


def pytest_collection_modifyitems(items):
    """Tag every test as unit or integration unless it says so itself.

    `live` tests call paid APIs, so they are always integration tests.
    """
    for item in items:
        if item.get_closest_marker("unit") or item.get_closest_marker(
            "integration"
        ):
            continue

        uses_services = INTEGRATION_FIXTURES.intersection(
            getattr(item, "fixturenames", ())
        )

        if item.get_closest_marker("live") or uses_services:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


class ScriptedLLM(BaseChatModel):
    """Offline chat model for agent tests that returns queued responses.

    Build a script with `call_tool`, `call_tools`, and `answer`; each agent
    LLM step consumes one entry. `keep_calling_tool` sets a fallback used
    once the queue is empty (e.g. to drive the max-iterations guard).

    It is a real chat model, so answers stream token by token through
    LangChain callbacks exactly like the Groq model does.
    """

    script: deque = Field(default_factory=deque)
    # Orchestrator route returned by the patched classifier.
    route: str = "general"
    # Supervisor decisions, consumed in order; "finish" once empty.
    supervisor_script: deque = Field(default_factory=deque)
    fallback: tuple[str, dict] | None = None
    next_call_id: int = 0
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    # (input_tokens, output_tokens) reported per call, like Groq does.
    usage: tuple[int, int] | None = None
    model_name: str = "scripted-model"

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs) -> "ScriptedLLM":
        return self

    def _tool_call(self, name: str, args: dict) -> dict:
        self.next_call_id += 1

        return {
            "name": name,
            "args": args,
            "id": f"call-{self.next_call_id}",
        }

    def call_tool(self, name: str, **args) -> "ScriptedLLM":
        return self.call_tools((name, args))

    def call_tools(self, *calls: tuple[str, dict]) -> "ScriptedLLM":
        self.script.append(
            [self._tool_call(name, args) for name, args in calls]
        )
        return self

    def answer(self, text: str) -> "ScriptedLLM":
        self.script.append(text)
        return self

    def keep_calling_tool(self, name: str, **args) -> "ScriptedLLM":
        self.fallback = (name, args)
        return self

    def route_to(self, route: str) -> "ScriptedLLM":
        self.route = route
        return self

    def supervise(self, *steps: tuple[str, str]) -> "ScriptedLLM":
        """Queue supervisor decisions as (worker, task) pairs."""
        self.supervisor_script.extend(steps)
        return self

    @property
    def remaining(self) -> int:
        return len(self.script)

    def _next_step(self, messages: list[BaseMessage]) -> str | list[dict]:
        self.calls.append(list(messages))

        if self.script:
            return self.script.popleft()

        if self.fallback is not None:
            name, args = self.fallback
            return [self._tool_call(name, args)]

        raise AssertionError(
            "ScriptedLLM has no response left for LLM call "
            f"#{len(self.calls)}"
        )

    def _usage_fields(self) -> dict:
        if self.usage is None:
            return {}

        input_tokens, output_tokens = self.usage

        return {
            "usage_metadata": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "response_metadata": {"model_name": self.model_name},
        }

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        step = self._next_step(messages)

        if isinstance(step, str):
            message = AIMessage(content=step, **self._usage_fields())
        else:
            message = AIMessage(
                content="",
                tool_calls=[{**call, "type": "tool_call"} for call in step],
                **self._usage_fields(),
            )

        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        step = self._next_step(messages)

        if not isinstance(step, str):
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    **self._usage_fields(),
                    tool_call_chunks=[
                        {
                            "name": call["name"],
                            "args": json.dumps(call["args"]),
                            "id": call["id"],
                            "index": index,
                            "type": "tool_call_chunk",
                        }
                        for index, call in enumerate(step)
                    ],
                )
            )
            return

        tokens = re.findall(r"\S+\s*", step)

        for index, token in enumerate(tokens):
            # Usage arrives once, on the final chunk.
            usage = self._usage_fields() if index == len(tokens) - 1 else {}
            chunk = ChatGenerationChunk(
                message=AIMessageChunk(content=token, **usage)
            )

            if run_manager:
                run_manager.on_llm_new_token(token, chunk=chunk)

            yield chunk


@pytest.fixture(autouse=True)
def force_chat_mock_mode(request, monkeypatch):
    """Keep non-live tests offline even when .env sets MOCK_MODE=false.

    Tests can still opt out by setting chat_service.MOCK_MODE themselves.
    """
    if request.node.get_closest_marker("live"):
        return

    from app.services import chat_service

    monkeypatch.setattr(chat_service, "MOCK_MODE", True)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Every test starts with empty rate-limit buckets."""
    from app.limiter import limiter

    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def fresh_agent_checkpointer():
    """Each test's agent runs are checkpointed in their own memory saver."""
    from langgraph.checkpoint.memory import InMemorySaver

    from app.agents import checkpoints

    saver = InMemorySaver()
    previous = checkpoints._checkpointer
    checkpoints.set_checkpointer(saver)

    yield saver

    checkpoints.set_checkpointer(previous)


@pytest.fixture
def scripted_llm(monkeypatch) -> ScriptedLLM:
    """Make agent graphs built in this test use a scripted, offline LLM.

    The orchestrator's classifier and the supervisor's decisions are
    scripted too: routing goes to the general tool agent unless the test
    calls `route_to`, and the supervisor follows `supervise(...)`.
    """
    from app.agents.router import RouteDecision
    from app.agents.supervisor import FINISH, SupervisorDecision

    llm = ScriptedLLM()

    async def classify(messages):
        return RouteDecision(route=llm.route, reason="scripted")

    async def decide_next(state):
        if not llm.supervisor_script:
            return SupervisorDecision(next=FINISH)

        worker, task = llm.supervisor_script.popleft()
        return SupervisorDecision(next=worker, task=task)

    monkeypatch.setattr(
        "app.agents.calculator_agent.create_tool_llm",
        lambda **kwargs: llm,
    )
    monkeypatch.setattr("app.agents.router.classify_message", classify)
    monkeypatch.setattr("app.agents.supervisor.decide_next", decide_next)

    return llm


@pytest.fixture
def mongo_down(client, monkeypatch):
    """Point the app at a MongoDB that refuses connections.

    Port 1 is never a MongoDB server, so every query fails fast with
    ServerSelectionTimeoutError, as it would during a real outage.
    """
    unreachable = AsyncMongoClient(
        "mongodb://127.0.0.1:1",
        serverSelectionTimeoutMS=200,
        connectTimeoutMS=200,
    )

    monkeypatch.setattr(db, "database", unreachable[TEST_DB_NAME])

    yield client


@pytest.fixture
def isolated_rag_service(tmp_path):
    """RAGService on a temporary Chroma collection with fake models.

    By default every chunk and query embeds to the same vector, so access
    and metadata filters alone decide what is returned. Tests can change
    `service.embedding_service.embed_query.return_value`; the reranker
    keeps every candidate and the answerability check always passes.
    """
    store = VectorStoreService(
        persist_directory=str(tmp_path / "chroma"),
        collection_name="ingestion_test",
        embedding_model="test-embedding-model",
    )

    with (
        patch("app.services.rag_service.EmbeddingService") as embedding,
        patch("app.services.rag_service.VectorStoreService", return_value=store),
        patch("app.services.rag_service.RerankerService") as reranker,
        patch("app.services.rag_service.AnswerabilityService") as answerability,
    ):
        embedding.return_value.embed_documents = AsyncMock(
            side_effect=lambda chunks: [[1.0, 0.0, 0.0] for _ in chunks]
        )
        embedding.return_value.embed_query = AsyncMock(
            return_value=[1.0, 0.0, 0.0]
        )
        reranker.return_value.rerank = MagicMock(
            side_effect=lambda query, documents, top_k: [
                {**document, "rerank_score": 1.0} for document in documents
            ]
        )
        answerability.return_value.evaluate = AsyncMock(
            return_value=AnswerabilityResult(is_answerable=True, reason="ok")
        )

        yield RAGService()


@pytest.fixture(scope="session")
def test_db():
    test_database = db.client[TEST_DB_NAME]
    original_database = db.database
    original_lifespan = app.router.lifespan_context

    db.database = test_database

    @asynccontextmanager
    async def test_lifespan(app):
        await db.create_users_index()
        await db.create_token_usage_index()
        await db.create_chat_history_indexes()
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
            "token_usage",
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


@pytest.fixture
def user_token(auth_headers):
    return auth_headers["Authorization"].removeprefix("Bearer ")


@pytest.fixture
def admin_token(client):
    payload = {
        "email": "admin-test@example.com",
        "password": "StrongPass123!",
    }

    register_response = client.post(
        "/api/auth/register",
        json=payload,
    )
    assert register_response.status_code == 201

    with MongoClient(MONGODB_URI) as sync_client:
        sync_client[TEST_DB_NAME]["users"].update_one(
            {"email": payload["email"]},
            {"$set": {"role": "admin"}},
        )

    login_response = client.post(
        "/api/auth/login",
        json=payload,
    )
    assert login_response.status_code == 200

    return login_response.json()["access_token"]