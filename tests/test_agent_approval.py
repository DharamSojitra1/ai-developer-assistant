import asyncio

import pytest

from app.security import decode_token
from app.services.rag_service import Requester

DELETE_REQUEST = {"message": "Delete my document doc-notes"}


@pytest.fixture
def user_id(user_token) -> str:
    return decode_token(user_token)["sub"]


@pytest.fixture
def knowledge_base(isolated_rag_service, monkeypatch):
    """The delete tool works on a temporary knowledge base."""
    monkeypatch.setattr(
        "app.tools.delete_document.rag_service",
        isolated_rag_service,
    )
    return isolated_rag_service


def index(knowledge_base, text: str, source: str, owner: str) -> None:
    asyncio.run(
        knowledge_base.index_document(
            text,
            document_id="doc-notes",
            source=source,
            visibility="private",
            requester=Requester(user_id=owner),
        )
    )


@pytest.fixture
def owned_document(knowledge_base, user_id):
    index(
        knowledge_base,
        "Personal deployment notes for the staging cluster.",
        "notes.md",
        user_id,
    )
    return "doc-notes"


def document_exists(knowledge_base, document_id: str) -> bool:
    return knowledge_base.vector_store.get_document_metadata(document_id) is not None


def start_deletion(client, auth_headers, scripted_llm, *extra_calls):
    scripted_llm.call_tools(
        *extra_calls,
        ("delete_my_document", {"document_id": "doc-notes"}),
    )

    response = client.post(
        "/api/agent/chat",
        json=DELETE_REQUEST,
        headers=auth_headers,
    )

    assert response.status_code == 200
    return response.json()


def history_count(client, auth_headers) -> int:
    return client.get("/api/chat/history", headers=auth_headers).json()["count"]


def test_deletion_pauses_for_approval(
    client, auth_headers, scripted_llm, owned_document, knowledge_base
):
    body = start_deletion(client, auth_headers, scripted_llm)

    assert body["status"] == "awaiting_approval"
    assert body["route"] == "general"
    assert body["approval"] == [
        {
            "tool_call_id": "call-1",
            "action": "delete_document",
            "document_id": "doc-notes",
            "source": "notes.md",
            "found": True,
        }
    ]
    assert f"/api/agent/runs/{body['run_id']}/approval" in body["response"]
    assert document_exists(knowledge_base, "doc-notes")
    assert history_count(client, auth_headers) == 0


def test_approval_deletes_the_document(
    client, auth_headers, scripted_llm, owned_document, knowledge_base
):
    body = start_deletion(client, auth_headers, scripted_llm)
    scripted_llm.answer("Your document was deleted.")

    response = client.post(
        f"/api/agent/runs/{body['run_id']}/approval",
        json={"approved": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["response"] == "Your document was deleted."
    assert not document_exists(knowledge_base, "doc-notes")

    history = client.get("/api/chat/history", headers=auth_headers).json()
    assert history["count"] == 1
    assert history["history"][0]["message"] == DELETE_REQUEST["message"]


def test_rejection_keeps_the_document(
    client, auth_headers, scripted_llm, owned_document, knowledge_base
):
    body = start_deletion(client, auth_headers, scripted_llm)
    scripted_llm.answer("Okay, I kept it.")

    response = client.post(
        f"/api/agent/runs/{body['run_id']}/approval",
        json={"approved": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert document_exists(knowledge_base, "doc-notes")

    declined = scripted_llm.calls[-1][-1]
    assert declined.name == "delete_my_document"
    assert "did not approve" in declined.content


def test_another_users_approval_is_not_found(
    client, auth_headers, admin_token, scripted_llm, owned_document
):
    body = start_deletion(client, auth_headers, scripted_llm)

    response = client.post(
        f"/api/agent/runs/{body['run_id']}/approval",
        json={"approved": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


def test_unknown_run_is_not_found(client, auth_headers):
    response = client.post(
        "/api/agent/runs/no-such-run/approval",
        json={"approved": True},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_repeated_approval_conflicts(
    client, auth_headers, scripted_llm, owned_document
):
    body = start_deletion(client, auth_headers, scripted_llm)
    scripted_llm.answer("Deleted.")
    url = f"/api/agent/runs/{body['run_id']}/approval"

    first = client.post(url, json={"approved": True}, headers=auth_headers)
    second = client.post(url, json={"approved": True}, headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 409


def test_parallel_call_is_not_rerun_on_resume(
    client, auth_headers, scripted_llm, owned_document, monkeypatch
):
    from app.tools.calculator import calculator

    evaluations = []
    original = calculator.func
    monkeypatch.setattr(
        calculator,
        "func",
        lambda expression: evaluations.append(expression) or original(expression),
    )

    body = start_deletion(
        client,
        auth_headers,
        scripted_llm,
        ("calculator", {"expression": "2 + 2"}),
    )
    scripted_llm.answer("Done: 4, and deleted.")

    response = client.post(
        f"/api/agent/runs/{body['run_id']}/approval",
        json={"approved": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert evaluations == ["2 + 2"]


@pytest.mark.asyncio
async def test_stream_ends_with_approval_note_when_paused(
    scripted_llm, knowledge_base, monkeypatch
):
    from unittest.mock import AsyncMock

    from app.agents import agent_service

    monkeypatch.setattr(
        agent_service, "get_recent_chat_history", AsyncMock(return_value=[])
    )
    scripted_llm.call_tool("delete_my_document", document_id="doc-notes")

    outcome = {}
    text = "".join(
        [
            chunk
            async for chunk in agent_service.stream_agent_response(
                user_id="user-1",
                message="Delete doc-notes",
                run_id="run-stream",
                outcome=outcome,
            )
        ]
    )

    assert outcome["status"] == "awaiting_approval"
    assert outcome["approval"][0]["document_id"] == "doc-notes"
    assert "/api/agent/runs/run-stream/approval" in text


def test_cannot_delete_someone_elses_document(
    client, auth_headers, scripted_llm, knowledge_base
):
    index(
        knowledge_base,
        "Someone else's private notes.",
        "theirs.md",
        "another-user",
    )

    body = start_deletion(client, auth_headers, scripted_llm)

    # The approval prompt does not reveal another user's document.
    assert body["approval"][0]["found"] is False
    assert body["approval"][0]["source"] is None

    scripted_llm.answer("I could not delete it.")
    client.post(
        f"/api/agent/runs/{body['run_id']}/approval",
        json={"approved": True},
        headers=auth_headers,
    )

    assert document_exists(knowledge_base, "doc-notes")
    assert "own documents" in scripted_llm.calls[-1][-1].content
