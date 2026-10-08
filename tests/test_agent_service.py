from uuid import uuid4

import pytest

from app import database as db
from app.agents.agent_service import build_agent_messages


@pytest.mark.asyncio
async def test_build_agent_messages(async_test_db):
    user_id = f"test-user-{uuid4()}"

    await db.save_chat_history(
        user_id=user_id,
        message="My favorite programming language is Java",
        response="Got it, your favorite programming language is Java.",
        model="test-model",
    )

    try:
        messages = await build_agent_messages(
            user_id=user_id,
            message="What is my favorite programming language?",
        )

        assert messages == [
            ("human", "My favorite programming language is Java"),
            ("ai", "Got it, your favorite programming language is Java."),
            ("human", "What is my favorite programming language?"),
        ]
    finally:
        await async_test_db["chat_history"].delete_many({"user_id": user_id})


@pytest.mark.asyncio
async def test_build_agent_messages_without_history(async_test_db):
    messages = await build_agent_messages(
        user_id=f"test-user-{uuid4()}",
        message="Hello",
    )

    assert messages == [("human", "Hello")]
