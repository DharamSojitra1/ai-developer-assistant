import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.calculator_agent import (
    MAX_ITERATIONS,
    collect_tool_calls,
    create_agent_graph,
)
from app.tools.tool_result import tool_error, tool_success


def calculator_call(call_id: str, expression: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "calculator",
                "args": {"expression": expression},
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


def test_collect_tool_calls_records_name_args_and_status():
    state = {
        "messages": [
            calculator_call("call-1", "2 + 2"),
            ToolMessage(
                content=tool_success("4"),
                name="calculator",
                tool_call_id="call-1",
            ),
            calculator_call("call-2", "1 / 0"),
            ToolMessage(
                content=tool_error("Cannot divide by zero."),
                name="calculator",
                tool_call_id="call-2",
            ),
        ],
    }

    result = collect_tool_calls(state)

    assert result["tool_calls"] == [
        {
            "name": "calculator",
            "args": {"expression": "2 + 2"},
            "status": "success",
        },
        {
            "name": "calculator",
            "args": {"expression": "1 / 0"},
            "status": "error",
        },
    ]


def test_collect_tool_calls_marks_tool_node_errors():
    state = {
        "messages": [
            calculator_call("call-1", "2 + 2"),
            ToolMessage(
                content="RuntimeError('boom')",
                name="calculator",
                tool_call_id="call-1",
                status="error",
            ),
        ],
    }

    result = collect_tool_calls(state)

    assert result["tool_calls"][0]["status"] == "error"


@pytest.mark.asyncio
async def test_stop_reason_is_final_answer_when_llm_answers(scripted_llm):
    scripted_llm.answer("Hello!")

    result = await create_agent_graph().ainvoke(
        {"messages": [("human", "Hi")]}
    )

    assert result["stop_reason"] == "final_answer"
    assert result.get("tool_calls", []) == []


@pytest.mark.asyncio
async def test_stop_reason_is_max_iterations_when_limit_reached(scripted_llm):
    scripted_llm.keep_calling_tool("calculator", expression="1 + 1")

    result = await create_agent_graph().ainvoke(
        {"messages": [("human", "Loop forever")]}
    )

    assert len(scripted_llm.calls) == MAX_ITERATIONS
    assert result["stop_reason"] == "max_iterations"
    assert result["iteration_count"] == MAX_ITERATIONS
    assert len(result["tool_calls"]) == MAX_ITERATIONS - 1
    assert all(
        call["name"] == "calculator" and call["status"] == "success"
        for call in result["tool_calls"]
    )
