import pytest

from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_relevant_query_returns_sources():
    service = RAGService()

    results = await service.retrieve(
        query="What is Generative AI?",
        top_k=3,
    )

    assert results
    assert results[0]["distance"] <= 0.35


@pytest.mark.asyncio
async def test_irrelevant_query_returns_no_sources():
    service = RAGService()

    results = await service.retrieve(
        query="What is the history of quantum computing?",
        top_k=3,
    )

    assert results == []