import pytest

from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_rag_falls_back_when_reranker_fails(monkeypatch):
    service = RAGService()

    retrieved_documents = [
        {
            "id": "doc-1",
            "text": "FastAPI is a Python web framework.",
            "distance": 0.20,
            "metadata": {"document_id": "fastapi-basics"},
        },
        {
            "id": "doc-2",
            "text": "Python is a programming language.",
            "distance": 0.25,
            "metadata": {"document_id": "python-basics"},
        },
        {
            "id": "doc-3",
            "text": "Generative AI generates new content.",
            "distance": 0.30,
            "metadata": {"document_id": "gen-ai-basics"},
        },
        {
            "id": "doc-4",
            "text": "Quantum computing uses quantum mechanics.",
            "distance": 0.50,
            "metadata": {"document_id": "quantum-basics"},
        },
    ]

    async def mock_embed_query(query):
        return [0.1, 0.2, 0.3]

    def mock_search(query_embedding, top_k):
        return retrieved_documents

    def mock_rerank(query, documents, top_k):
        raise RuntimeError("Simulated reranker failure")

    monkeypatch.setattr(
        service.embedding_service,
        "embed_query",
        mock_embed_query,
    )
    monkeypatch.setattr(
        service.vector_store,
        "search",
        mock_search,
    )
    monkeypatch.setattr(
        service.reranker_service,
        "rerank",
        mock_rerank,
    )

    results = await service.retrieve("What is FastAPI?")

    assert len(results) == 3
    assert all(
        result["distance"] <= 0.35
        for result in results
    )
    assert all(
        "rerank_score" not in result
        for result in results
    )
    assert [
        result["metadata"]["document_id"]
        for result in results
    ] == [
        "fastapi-basics",
        "python-basics",
        "gen-ai-basics",
    ]