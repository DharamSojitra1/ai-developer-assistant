from uuid import uuid4

import pytest

from app import database as db
from app.agents.agent_service import build_agent_messages
from app.agents.calculator_agent import graph


@pytest.mark.asyncio
async def test_agent_with_memory(async_test_db):
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
            message="What did I tell you about my favorite programming language?",
        )

        result = await graph.ainvoke(
            {
                "messages": messages,
                "iteration_count": 0,
            }
        )
    finally:
        await async_test_db["chat_history"].delete_many({"user_id": user_id})

    final_message = result["messages"][-1]

    print("\nAGENT MEMORY RESPONSE:")
    print(final_message.content)

    assert "java" in final_message.content.lower()
