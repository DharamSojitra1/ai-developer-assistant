import asyncio
from uuid import uuid4

import pytest

from app import database as db
from app.security import decode_token
from app.services.rag_service import Requester


def new_id() -> str:
    return str(uuid4())


def stream_chat(client, auth_headers, message: str, conversation_id: str | None = None):
    body = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id

    response = client.post("/api/chat/chat/stream", json=body, headers=auth_headers)
    assert response.status_code == 200
    return response


def list_conversations(client, headers) -> list[dict]:
    response = client.get("/api/chat/conversations", headers=headers)
    assert response.status_code == 200
    return response.json()["conversations"]


def human_messages(llm_call) -> list[str]:
    return [message.content for message in llm_call if message.type == "human"]


def test_messages_in_a_conversation_are_listed_once(client, auth_headers):
    first, second = new_id(), new_id()

    stream_chat(client, auth_headers, "Call me King", first)
    stream_chat(client, auth_headers, "What is my name?", first)
    stream_chat(client, auth_headers, "Unrelated question", second)

    conversations = list_conversations(client, auth_headers)

    assert [item["id"] for item in conversations] == [second, first]
    assert conversations[1]["title"] == "Call me King"
    assert conversations[1]["message_count"] == 2
    assert conversations[0]["message_count"] == 1


def test_stream_reports_the_conversation_id(client, auth_headers):
    conversation_id = new_id()

    given = stream_chat(client, auth_headers, "Hi", conversation_id)
    started = stream_chat(client, auth_headers, "Hello")

    assert given.headers["X-Conversation-ID"] == conversation_id
    assert started.headers["X-Conversation-ID"] not in ("", conversation_id)
    assert {item["id"] for item in list_conversations(client, auth_headers)} == {
        conversation_id,
        started.headers["X-Conversation-ID"],
    }


def test_conversation_titles_are_shortened(client, auth_headers):
    stream_chat(client, auth_headers, "x" * 200, new_id())

    assert list_conversations(client, auth_headers)[0]["title"] == "x" * 80


def test_get_conversation_returns_the_thread_oldest_first(client, auth_headers):
    conversation_id = new_id()
    stream_chat(client, auth_headers, "First", conversation_id)
    stream_chat(client, auth_headers, "Second", conversation_id)

    response = client.get(f"/api/chat/conversations/{conversation_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == conversation_id
    assert [item["message"] for item in body["messages"]] == ["First", "Second"]
    assert body["messages"][0]["response"] == "Mock response: First"
    assert body["messages"][0]["conversation_id"] == conversation_id


def test_unknown_conversation_is_not_found(client, auth_headers):
    response = client.get(f"/api/chat/conversations/{new_id()}", headers=auth_headers)

    assert response.status_code == 404


def test_another_users_conversation_is_not_found(client, auth_headers, admin_token):
    conversation_id = new_id()
    stream_chat(client, auth_headers, "Private question", conversation_id)
    other = {"Authorization": f"Bearer {admin_token}"}

    read = client.get(f"/api/chat/conversations/{conversation_id}", headers=other)
    delete = client.delete(f"/api/chat/conversations/{conversation_id}", headers=other)

    assert read.status_code == 404
    assert delete.status_code == 404
    assert list_conversations(client, other) == []
    assert len(list_conversations(client, auth_headers)) == 1


def test_delete_conversation_removes_only_that_conversation(client, auth_headers):
    kept, removed = new_id(), new_id()
    stream_chat(client, auth_headers, "Keep me", kept)
    stream_chat(client, auth_headers, "Remove me", removed)
    stream_chat(client, auth_headers, "Remove me too", removed)

    response = client.delete(f"/api/chat/conversations/{removed}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    assert [item["id"] for item in list_conversations(client, auth_headers)] == [kept]


@pytest.mark.parametrize("bad_id", ["short", "has spaces in it", "x" * 65, "semi;colon!"])
def test_invalid_conversation_ids_are_rejected(client, auth_headers, bad_id):
    chat = client.post(
        "/api/chat/chat/stream",
        json={"message": "Hi", "conversation_id": bad_id},
        headers=auth_headers,
    )
    read = client.get(f"/api/chat/conversations/{bad_id}", headers=auth_headers)

    assert chat.status_code == 422
    assert read.status_code in (404, 422)


def test_conversation_endpoints_require_auth(client):
    assert client.get("/api/chat/conversations").status_code in (401, 403)
    assert client.get(f"/api/chat/conversations/{new_id()}").status_code in (401, 403)
    assert client.delete(f"/api/chat/conversations/{new_id()}").status_code in (401, 403)


def test_agent_context_is_scoped_to_the_conversation(client, auth_headers, scripted_llm):
    first, second = new_id(), new_id()

    def ask(message: str, conversation_id: str) -> dict:
        scripted_llm.answer(f"Answer to {message}")
        response = client.post(
            "/api/agent/chat",
            json={"message": message, "conversation_id": conversation_id},
            headers=auth_headers,
        )
        assert response.status_code == 200
        return response.json()

    reply = ask("Call me King", first)
    ask("What is my name?", second)
    second_context = human_messages(scripted_llm.calls[-1])
    ask("What is my name?", first)
    first_context = human_messages(scripted_llm.calls[-1])

    assert reply["conversation_id"] == first
    assert "Call me King" not in second_context
    assert first_context[-2:] == ["Call me King", "What is my name?"]


def test_agent_without_conversation_id_starts_a_new_conversation(
    client, auth_headers, scripted_llm
):
    scripted_llm.answer("Hello!")

    response = client.post("/api/agent/chat", json={"message": "Hi"}, headers=auth_headers)

    conversation_id = response.json()["conversation_id"]
    assert conversation_id
    assert [item["id"] for item in list_conversations(client, auth_headers)] == [conversation_id]


@pytest.mark.asyncio
async def test_context_without_a_conversation_spans_all_conversations(async_test_db):
    user_id = f"test-user-{uuid4()}"
    first, second = new_id(), new_id()

    try:
        await db.save_chat_history(user_id, "In first", "ok", "m", conversation_id=first)
        await db.save_chat_history(user_id, "In second", "ok", "m", conversation_id=second)

        everything = await db.get_recent_chat_history(user_id)
        scoped = await db.get_recent_chat_history(user_id, conversation_id=first)
    finally:
        await async_test_db["chat_history"].delete_many({"user_id": user_id})

    assert [item["message"] for item in everything] == ["In first", "In second"]
    assert [item["message"] for item in scoped] == ["In first"]


@pytest.mark.asyncio
async def test_legacy_turns_are_backfilled_into_their_own_conversations(async_test_db):
    user_id = f"test-user-{uuid4()}"
    collection = async_test_db["chat_history"]

    try:
        result = await collection.insert_one(
            {"user_id": user_id, "message": "old", "response": "ok", "model": "m"}
        )
        await db.create_chat_history_indexes()
        document = await collection.find_one({"_id": result.inserted_id})
    finally:
        await collection.delete_many({"user_id": user_id})

    assert document["conversation_id"] == str(result.inserted_id)


@pytest.fixture
def owned_document(isolated_rag_service, user_token, monkeypatch):
    monkeypatch.setattr("app.tools.delete_document.rag_service", isolated_rag_service)
    asyncio.run(
        isolated_rag_service.index_document(
            "Personal deployment notes.",
            document_id="doc-notes",
            source="notes.md",
            visibility="private",
            requester=Requester(user_id=decode_token(user_token)["sub"]),
        )
    )
    return "doc-notes"


def test_approved_run_is_saved_in_its_conversation(
    client, auth_headers, scripted_llm, owned_document
):
    conversation_id = new_id()
    scripted_llm.call_tool("delete_my_document", document_id=owned_document)

    paused = client.post(
        "/api/agent/chat",
        json={"message": "Delete doc-notes", "conversation_id": conversation_id},
        headers=auth_headers,
    ).json()
    assert paused["status"] == "awaiting_approval"
    assert paused["conversation_id"] == conversation_id

    scripted_llm.answer("Deleted.")
    resumed = client.post(
        f"/api/agent/runs/{paused['run_id']}/approval",
        json={"approved": True},
        headers=auth_headers,
    ).json()

    assert resumed["status"] == "completed"
    assert resumed["conversation_id"] == conversation_id
    thread = client.get(f"/api/chat/conversations/{conversation_id}", headers=auth_headers)
    assert [item["message"] for item in thread.json()["messages"]] == ["Delete doc-notes"]
