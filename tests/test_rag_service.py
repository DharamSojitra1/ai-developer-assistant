import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag_service import RAGService


@pytest.fixture
def rag_service():
    with (
        patch("app.services.rag_service.EmbeddingService") as mock_embedding,
        patch("app.services.rag_service.VectorStoreService") as mock_store,
        patch("app.services.rag_service.split_document") as mock_split,
    ):
        embedding_instance = MagicMock()
        embedding_instance.embed_documents = AsyncMock(
            return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        )
        embedding_instance.embed_query = AsyncMock(
            return_value=[0.7, 0.8, 0.9]
        )

        store_instance = MagicMock()
        store_instance.search.return_value = [
            {
                "id": "doc1_0",
                "text": "FastAPI is a Python framework.",
                "distance": 0.1,
                "metadata": {"document_id": "doc1"},
            }
        ]

        mock_embedding.return_value = embedding_instance
        mock_store.return_value = store_instance
        mock_split.return_value = ["Chunk 1", "Chunk 2"]

        service = RAGService()

        yield service, embedding_instance, store_instance, mock_split


@pytest.mark.asyncio
async def test_index_document(rag_service):
    service, embedding, store, split = rag_service

    result = await service.index_document(
        text="FastAPI is a Python framework.",
        document_id="doc1",
    )

    assert result == {
        "document_id": "doc1",
        "chunks_indexed": 2,
    }

    split.assert_called_once()
    embedding.embed_documents.assert_awaited_once_with(
        ["Chunk 1", "Chunk 2"]
    )

    store.add_chunks.assert_called_once()
    kwargs = store.add_chunks.call_args.kwargs

    assert kwargs["ids"] == ["doc1_0", "doc1_1"]
    assert kwargs["chunks"] == ["Chunk 1", "Chunk 2"]


@pytest.mark.asyncio
async def test_retrieve(rag_service):
    service, embedding, store, _ = rag_service

    result = await service.retrieve(
        query="What is FastAPI?",
        top_k=3,
    )

    embedding.embed_query.assert_awaited_once_with(
        "What is FastAPI?"
    )

    store.search.assert_called_once_with(
        query_embedding=[0.7, 0.8, 0.9],
        top_k=3,
    )

    assert result[0]["text"] == "FastAPI is a Python framework."


@pytest.mark.asyncio
async def test_empty_document(rag_service):
    service, embedding, store, split = rag_service

    with pytest.raises(
        ValueError,
        match="Document text cannot be empty",
    ):
        await service.index_document("   ")

    split.assert_not_called()
    embedding.embed_documents.assert_not_awaited()
    store.add_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_empty_query(rag_service):
    service, embedding, store, _ = rag_service

    with pytest.raises(
        ValueError,
        match="Query cannot be empty",
    ):
        await service.retrieve("   ")

    embedding.embed_query.assert_not_awaited()
    store.search.assert_not_called()