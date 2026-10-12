import asyncio
import logging
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.agents.calculator_agent import create_agent_graph
from app.middleware import RequestIdMiddleware
from app.tools.calculator import calculator
from app.tools.text_analyzer import analyze_text
from app.utils.llm_logging import install_llm_logging
from app.utils.log_context import (
    LogContextFilter,
    bind_log_context,
    get_log_context,
    request_id_var,
)

install_llm_logging()


def records(caplog, message: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.message == message]


def fake_model(model_name="openai/gpt-oss-120b", content="ok"):
    return FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content=content,
                usage_metadata={
                    "input_tokens": 120,
                    "output_tokens": 30,
                    "total_tokens": 150,
                },
                response_metadata={
                    "model_name": model_name,
                    "finish_reason": "stop",
                },
            )
        ]
    )


@pytest.fixture
def caplog_info(caplog):
    caplog.set_level(logging.INFO)
    return caplog


# ------------------------------------------------------------ log context


def test_bind_log_context_sets_and_restores_values():
    assert get_log_context() == {}

    with bind_log_context(request_id="req-1"):
        with bind_log_context(run_id="run-1", user_id="user-1"):
            assert get_log_context() == {
                "request_id": "req-1",
                "run_id": "run-1",
                "user_id": "user-1",
            }

        assert get_log_context() == {"request_id": "req-1"}

    assert get_log_context() == {}


def test_bind_log_context_restores_on_error():
    with pytest.raises(RuntimeError):
        with bind_log_context(run_id="run-1"):
            raise RuntimeError

    assert get_log_context() == {}


def test_bind_log_context_rejects_unknown_fields():
    with pytest.raises(ValueError, match="session_id"):
        with bind_log_context(session_id="x"):
            pass


def test_filter_adds_context_without_overriding_explicit_extra():
    log_filter = LogContextFilter()
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
    record.run_id = "explicit-run"

    with bind_log_context(request_id="req-1", run_id="context-run"):
        assert log_filter.filter(record) is True

    assert record.request_id == "req-1"
    assert record.run_id == "explicit-run"
    assert not hasattr(record, "user_id")


@pytest.mark.asyncio
async def test_context_reaches_tasks_and_threads():
    def in_thread():
        return request_id_var.get()

    async def in_task():
        return request_id_var.get()

    with bind_log_context(request_id="req-1"):
        thread_value = await asyncio.to_thread(in_thread)
        task_value = await asyncio.create_task(in_task())

    assert thread_value == task_value == "req-1"


def test_middleware_binds_request_id_for_logs_inside_the_request(caplog_info):
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    endpoint_logger = logging.getLogger("test.endpoint")

    @app.get("/work")
    async def work():
        def blocking_step():
            endpoint_logger.info("Inside thread")

        endpoint_logger.info("Inside endpoint")
        await asyncio.to_thread(blocking_step)
        return {}

    caplog_info.handler.addFilter(LogContextFilter())

    with TestClient(app) as client:
        response = client.get("/work", headers={"X-Request-ID": "req-abc"})

    assert response.headers["X-Request-ID"] == "req-abc"
    assert [
        record.request_id
        for record in caplog_info.records
        if record.name == "test.endpoint"
    ] == ["req-abc", "req-abc"]
    assert get_log_context() == {}


# --------------------------------------------------------------- LLM calls


@pytest.mark.asyncio
async def test_llm_call_is_logged_with_model_latency_tokens_and_context(
    caplog_info,
):
    with bind_log_context(request_id="req-1", run_id="run-1", user_id="u-1"):
        await fake_model().ainvoke("hello")

    [record] = records(caplog_info, "LLM call completed")

    assert record.name == "agent.llm"
    assert record.model == "openai/gpt-oss-120b"
    assert record.latency_ms >= 0
    assert record.input_tokens == 120
    assert record.output_tokens == 30
    assert record.total_tokens == 150
    assert record.message_count == 1
    assert record.tool_call_count == 0
    assert record.finish_reason == "stop"
    assert (record.request_id, record.run_id, record.user_id) == (
        "req-1",
        "run-1",
        "u-1",
    )


@pytest.mark.asyncio
async def test_llm_failure_is_logged_with_error_type(caplog_info, scripted_llm):
    # An empty script makes the fake model raise.
    with pytest.raises(AssertionError):
        await scripted_llm.ainvoke("hello")

    [record] = records(caplog_info, "LLM call failed")

    assert record.levelno == logging.WARNING
    assert record.error_type == "AssertionError"
    assert record.latency_ms >= 0


@pytest.mark.asyncio
async def test_prompt_and_answer_text_are_not_logged(caplog_info):
    await fake_model(content="secret answer").ainvoke("secret prompt")

    [record] = records(caplog_info, "LLM call completed")

    assert "secret" not in str(record.__dict__)


# -------------------------------------------------------------- tool calls


@pytest.mark.asyncio
async def test_successful_tool_call_is_logged_with_latency(caplog_info):
    await calculator.ainvoke({"expression": "2 + 2"})

    [record] = records(caplog_info, "Agent tool executed")

    assert record.name == "agent.tools"
    assert record.tool_name == "calculator"
    assert record.tool_args == {"expression": "2 + 2"}
    assert record.tool_status == "success"
    assert record.latency_ms >= 0


@pytest.mark.asyncio
async def test_tool_returning_error_payload_is_logged_as_error(caplog_info):
    await calculator.ainvoke({"expression": "1 / 0"})

    [record] = records(caplog_info, "Agent tool executed")

    assert record.tool_status == "error"
    assert record.levelno == logging.WARNING


@pytest.mark.asyncio
async def test_crashing_tool_is_logged_with_error_type(caplog_info):
    @tool
    def exploding(text: str) -> str:
        """Always fails."""
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await exploding.ainvoke({"text": "x"})

    [record] = records(caplog_info, "Agent tool executed")

    assert record.tool_name == "exploding"
    assert record.tool_status == "error"
    assert record.error_type == "RuntimeError"


# ------------------------------------------------------- inside the agent


@pytest.mark.asyncio
async def test_agent_run_logs_every_llm_and_tool_call_with_run_context(
    caplog_info,
    scripted_llm,
):
    scripted_llm.call_tool("calculator", expression="25 * 4").answer("100")

    with bind_log_context(request_id="req-1", run_id="run-1", user_id="u-1"):
        await create_agent_graph().ainvoke(
            {"messages": [("human", "What is 25 * 4?")]}
        )

    llm_records = records(caplog_info, "LLM call completed")
    [tool_record] = records(caplog_info, "Agent tool executed")

    assert len(llm_records) == 2
    assert tool_record.tool_name == "calculator"
    assert tool_record.tool_args == {"expression": "25 * 4"}
    assert tool_record.tool_status == "success"

    for record in [*llm_records, tool_record]:
        assert record.request_id == "req-1"
        assert record.run_id == "run-1"
        assert record.user_id == "u-1"


@pytest.mark.asyncio
async def test_llm_call_nested_inside_a_tool_is_logged_with_run_context(
    caplog_info,
    scripted_llm,
):
    inner_model = fake_model(model_name="inner-model")

    def text_tool_calling_an_llm(text: str) -> str:
        # Like the answerability check inside search_knowledge_base.
        inner_model.invoke(text)
        return '{"ok": true, "result": {}, "error": null}'

    scripted_llm.call_tool("analyze_text", text="hi").answer("done")

    with (
        patch.object(analyze_text, "func", text_tool_calling_an_llm),
        bind_log_context(run_id="run-1"),
    ):
        await create_agent_graph().ainvoke({"messages": [("human", "Analyze hi")]})

    inner = [
        record
        for record in records(caplog_info, "LLM call completed")
        if record.model == "inner-model"
    ]

    assert len(inner) == 1
    assert inner[0].run_id == "run-1"
