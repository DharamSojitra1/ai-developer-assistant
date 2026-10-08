from uuid import uuid4

import pytest

from app.agents.agent_service import generate_agent_response


@pytest.mark.asyncio
async def test_agent_logs_tool_usage(caplog, async_test_db):
    user_id = f"test-user-{uuid4()}"

    try:
        with caplog.at_level("INFO", logger="agent"):
            result = await generate_agent_response(
                user_id=user_id,
                message="What is 25 * 4?",
                model="test-model",
            )
    finally:
        await async_test_db["chat_history"].delete_many({"user_id": user_id})

    assert result["response"]

    messages = [record.message for record in caplog.records]

    assert "Agent execution started" in messages
    assert "Agent execution completed" in messages

    tool_records = [
        record
        for record in caplog.records
        if record.message == "Agent tool executed"
    ]

    assert tool_records
    assert tool_records[0].tool_name == "calculator"
    assert tool_records[0].user_id == user_id
