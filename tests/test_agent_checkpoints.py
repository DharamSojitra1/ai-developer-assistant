import logging

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app import main
from app.agents import checkpoints
from app.agents.checkpoints import (
    CHECKPOINT_COLLECTION,
    create_mongo_checkpointer,
    get_checkpointer,
    run_config,
)
from app.agents.orchestrator import create_orchestrator_graph
from tests.conftest import TEST_DB_NAME


@pytest.fixture(autouse=True)
def knowledge_base(isolated_rag_service, monkeypatch):
    monkeypatch.setattr(
        "app.tools.delete_document.rag_service",
        isolated_rag_service,
    )


def deletion_state() -> dict:
    return {
        "messages": [("human", "Delete doc-1")],
        "user_id": "user-1",
        "approvals": {},
    }


async def pause_then_resume_in_new_graph(scripted_llm, saver, run_id):
    scripted_llm.call_tool("delete_my_document", document_id="doc-1")
    scripted_llm.answer("Okay, I kept it.")

    await create_orchestrator_graph(checkpointer=saver).ainvoke(
        deletion_state(), run_config(run_id)
    )

    # A fresh graph (e.g. after a restart) picks the run up from the saver.
    graph = create_orchestrator_graph(checkpointer=saver)
    snapshot = await graph.aget_state(run_config(run_id))

    assert snapshot.interrupts
    assert snapshot.values["user_id"] == "user-1"

    result = await graph.ainvoke(
        Command(resume={"approved": False}),
        run_config(run_id),
    )

    assert result["messages"][-1].content == "Okay, I kept it."
    assert not (await graph.aget_state(run_config(run_id))).interrupts


@pytest.mark.asyncio
async def test_run_resumes_from_a_new_graph_instance(scripted_llm):
    await pause_then_resume_in_new_graph(scripted_llm, InMemorySaver(), "run-1")


def test_runs_are_isolated_by_thread():
    assert run_config("a") != run_config("b")
    assert run_config("a")["configurable"]["thread_id"] == "a"


def test_default_checkpointer_is_in_memory(monkeypatch):
    monkeypatch.setattr(checkpoints, "_checkpointer", None)

    assert isinstance(get_checkpointer(), InMemorySaver)
    assert get_checkpointer() is get_checkpointer()


@pytest.mark.asyncio
async def test_lifespan_falls_back_when_mongo_saver_fails(monkeypatch, caplog):
    def unreachable():
        raise ConnectionError("mongo down")

    monkeypatch.setattr(main, "create_mongo_checkpointer", unreachable)

    with caplog.at_level(logging.WARNING):
        assert await main.open_agent_checkpointer() is None

    assert any("in-memory" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_mongo_saver_persists_and_resumes(test_db, scripted_llm):
    saver = create_mongo_checkpointer(db_name=TEST_DB_NAME, ttl=3600)

    try:
        await pause_then_resume_in_new_graph(scripted_llm, saver, "mongo-run")

        stored = saver.db[CHECKPOINT_COLLECTION].count_documents(
            {"thread_id": "mongo-run"}
        )
        assert stored > 0
    finally:
        saver.client.close()
