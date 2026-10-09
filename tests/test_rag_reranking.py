import pytest

from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_rag_retrieval_uses_reranker(monkeypatch):
    service = RAGService()

    retrieved_documents = [
        {
            "id": "doc-1",
            "text": "FastAPI is a modern Python web framework for building APIs.",
            "distance": 0.20,
            "metadata": {"document_id": "fastapi-basics"},
        },
        {
            "id": "doc-2",
            "text": "Python is a high-level programming language.",
            "distance": 0.21,
            "metadata": {"document_id": "python-basics"},
        },
    ]

    async def mock_embed_query(query):
        return [0.1, 0.2, 0.3]

    def mock_search(query_embedding, top_k):
        assert top_k == 10
        return retrieved_documents

    def mock_rerank(query, documents, top_k):
        assert query == "What is FastAPI?"
        assert documents == retrieved_documents
        assert top_k == 3

        return [
            {
                **retrieved_documents[0],
                "rerank_score": 0.95,
            }
        ]

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

    assert len(results) == 1
    assert results[0]["metadata"]["document_id"] == "fastapi-basics"
    assert results[0]["rerank_score"] == 0.95