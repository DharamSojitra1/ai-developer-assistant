import logging

import pytest
from pymongo import MongoClient

from app import database as db
from app.config import MONGODB_URI
from app.utils.redaction import RedactionFilter, redact_text, redact_tool_args
from tests.conftest import TEST_DB_NAME


# ------------------------------------------------------------ tool args


def test_free_text_tool_args_are_logged_as_lengths():
    assert redact_tool_args({"query": "my salary is 90k"}) == {
        "query": "<redacted len=16>"
    }
    assert redact_tool_args({"text": "Dear Bob, ..."}) == {
        "text": "<redacted len=13>"
    }


def test_short_debugging_args_are_kept():
    assert redact_tool_args({"expression": "2 + 2"}) == {"expression": "2 + 2"}
    assert redact_tool_args({"document_id": "doc-1"}) == {"document_id": "doc-1"}


def test_long_allowlisted_args_are_redacted():
    assert redact_tool_args({"expression": "1+" * 200}) == {
        "expression": "<redacted len=400>"
    }


def test_injected_state_is_never_logged():
    args = {
        "document_id": "doc-1",
        "state": {"messages": ["the whole conversation"]},
        "tool_call_id": "call-1",
    }

    assert redact_tool_args(args) == {"document_id": "doc-1"}


def test_raw_string_input_is_redacted():
    assert redact_tool_args("some text") == "<redacted len=9>"


@pytest.mark.asyncio
async def test_agent_tool_log_redacts_free_text(scripted_llm, caplog):
    from app.agents.calculator_agent import create_agent_graph

    scripted_llm.call_tool("analyze_text", text="Call me at 555-0100").answer("ok")

    with caplog.at_level(logging.INFO, logger="agent.tools"):
        await create_agent_graph().ainvoke({"messages": [("human", "Analyze")]})

    [record] = [r for r in caplog.records if r.message == "Agent tool executed"]

    assert record.tool_args == {"text": "<redacted len=19>"}


# ---------------------------------------------------------- log records


def test_emails_and_tokens_are_masked():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl"

    assert redact_text("contact a.b@example.com") == "contact <redacted email>"
    assert "eyJ" not in redact_text(f"token {jwt}")
    assert redact_text("Authorization: Bearer abc.def") == (
        "Authorization: Bearer <redacted token>"
    )


def test_redaction_filter_masks_message_args_and_extras():
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1,
        "Login for %s", ("jane@example.com",), None,
    )
    record.email = "jane@example.com"
    record.nested = {"to": ["bob@example.com"]}

    assert RedactionFilter().filter(record)

    assert record.getMessage() == "Login for <redacted email>"
    assert record.email == "<redacted email>"
    assert record.nested == {"to": ["<redacted email>"]}


# ------------------------------------------------------------ retention


def chat_history_indexes() -> dict:
    with MongoClient(MONGODB_URI) as sync_client:
        return sync_client[TEST_DB_NAME]["chat_history"].index_information()


def test_chat_history_has_a_ttl_index(client):
    ttl = chat_history_indexes()[db.CHAT_HISTORY_TTL_INDEX]

    assert ttl["expireAfterSeconds"] == db.CHAT_HISTORY_RETENTION_DAYS * 86400


@pytest.mark.asyncio
async def test_retention_change_is_applied(async_test_db):
    await db.create_chat_history_indexes(retention_days=30)
    changed = chat_history_indexes()[db.CHAT_HISTORY_TTL_INDEX]

    await db.create_chat_history_indexes()
    restored = chat_history_indexes()[db.CHAT_HISTORY_TTL_INDEX]

    assert changed["expireAfterSeconds"] == 30 * 86400
    assert restored["expireAfterSeconds"] == db.CHAT_HISTORY_RETENTION_DAYS * 86400


def test_user_can_delete_their_history(client, auth_headers, admin_token):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    for headers in (auth_headers, auth_headers, admin_headers):
        client.post("/api/chat/chat", json={"message": "hi"}, headers=headers)

    response = client.delete("/api/chat/history", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    assert client.get("/api/chat/history", headers=auth_headers).json()["count"] == 0
    # Other users' history is untouched.
    assert client.get("/api/chat/history", headers=admin_headers).json()["count"] == 1


def test_deleting_history_requires_auth(client):
    assert client.delete("/api/chat/history").status_code in (401, 403)
