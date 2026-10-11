from uuid import uuid4

import pytest

from app.agents.agent_service import generate_agent_response

pytestmark = pytest.mark.live


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
    assert tool_records[0].tool_args
    assert tool_records[0].tool_status == "success"
    assert tool_records[0].latency_ms >= 0

    llm_records = [
        record
        for record in caplog.records
        if record.message == "LLM call completed"
    ]

    assert len(llm_records) >= 2
    for record in llm_records:
        assert record.model
        assert record.latency_ms > 0
        assert record.input_tokens > 0
        assert record.output_tokens > 0

    started = next(
        record
        for record in caplog.records
        if record.message == "Agent execution started"
    )
    completed = next(
        record
        for record in caplog.records
        if record.message == "Agent execution completed"
    )

    assert started.run_id
    assert completed.run_id == started.run_id
    assert tool_records[0].run_id == started.run_id
    assert all(record.run_id == started.run_id for record in llm_records)
    assert completed.stop_reason == "final_answer"
    assert completed.tool_calls == [{"name": "calculator", "status": "success"}]
    assert completed.duration_ms >= 0
    assert completed.ended_at >= completed.started_at
