import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag_service import RAGService
from app.tools.rag_search import search_knowledge_base
from app.tools.tool_result import with_timeout


@pytest.mark.asyncio
async def test_with_timeout_returns_result_when_fast():
    @with_timeout("too slow", seconds=1)
    async def fast():
        return "done"

    assert await fast() == "done"


@pytest.mark.asyncio
async def test_with_timeout_returns_structured_error_when_slow():
    @with_timeout("too slow", seconds=0.05)
    async def slow():
        await asyncio.sleep(5)

    start = time.perf_counter()
    result = json.loads(await slow())

    assert result == {"ok": False, "result": None, "error": "too slow"}
    assert time.perf_counter() - start < 1


@pytest.mark.asyncio
async def test_knowledge_base_search_times_out():
    async def slow_retrieve(query, user_id=None):
        await asyncio.sleep(5)

    with (
        patch.object(search_knowledge_base.coroutine, "timeout_seconds", 0.05),
        patch(
            "app.tools.rag_search.rag_service.retrieve",
            side_effect=slow_retrieve,
        ),
    ):
        start = time.perf_counter()
        payload = json.loads(
            await search_knowledge_base.ainvoke({"query": "anything"})
        )

    assert payload["ok"] is False
    assert "timed out" in payload["error"]
    assert time.perf_counter() - start < 1


@pytest.fixture
def rag_service_with_blocking_store():
    with (
        patch("app.services.rag_service.EmbeddingService") as mock_embedding,
        patch("app.services.rag_service.VectorStoreService") as mock_store,
        patch("app.services.rag_service.RerankerService"),
        patch("app.services.rag_service.AnswerabilityService"),
    ):
        embedding_instance = MagicMock()
        embedding_instance.embed_query = AsyncMock(return_value=[0.1])

        store_instance = MagicMock()
        store_instance.search.side_effect = lambda **kwargs: time.sleep(1)

        mock_embedding.return_value = embedding_instance
        mock_store.return_value = store_instance

        yield RAGService()


@pytest.mark.asyncio
async def test_blocking_vector_search_does_not_block_event_loop(
    rag_service_with_blocking_store,
):
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    ticker_task = asyncio.create_task(ticker())
    start = time.perf_counter()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            rag_service_with_blocking_store.retrieve(query="anything"),
            timeout=0.1,
        )

    elapsed = time.perf_counter() - start
    ticker_task.cancel()

    assert elapsed < 0.5
    assert ticks > 0
