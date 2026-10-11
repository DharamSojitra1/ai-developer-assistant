import json
from unittest.mock import patch

import pytest
from langchain_core.messages import ToolMessage

from app.agents.calculator_agent import create_agent_graph
from app.tools.text_analyzer import analyze_text
from app.tools.tool_result import UNEXPECTED_TOOL_ERROR, handle_tool_exception


def crashing_tool(text: str) -> str:
    raise RuntimeError("secret internal detail at 10.0.0.5")


def test_handle_tool_exception_hides_details():
    payload = json.loads(
        handle_tool_exception(RuntimeError("secret internal detail"))
    )

    assert payload == {
        "ok": False,
        "result": None,
        "error": UNEXPECTED_TOOL_ERROR,
    }


@pytest.mark.asyncio
async def test_agent_returns_structured_error_when_tool_crashes(
    caplog,
    scripted_llm,
):
    scripted_llm.call_tool("analyze_text", text="hello").answer(
        "Sorry, the tool failed."
    )

    with (
        patch.object(analyze_text, "func", crashing_tool),
        caplog.at_level("ERROR", logger="agent"),
    ):
        result = await create_agent_graph().ainvoke(
            {"messages": [("human", "Analyze: hello")]}
        )

    tool_message = next(
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage)
    )

    assert json.loads(tool_message.content) == {
        "ok": False,
        "result": None,
        "error": UNEXPECTED_TOOL_ERROR,
    }
    assert "secret internal detail" not in tool_message.content

    assert result["tool_calls"] == [
        {
            "name": "analyze_text",
            "args": {"text": "hello"},
            "status": "error",
        }
    ]
    assert result["stop_reason"] == "final_answer"

    assert any(
        "secret internal detail" in str(record.exc_info[1])
        for record in caplog.records
        if record.exc_info
    )
