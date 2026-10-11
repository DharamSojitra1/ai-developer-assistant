import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.answerability_service import AnswerabilityResult
from app.services.document_service import Chunk
from app.services.rag_service import RAGService


@pytest.fixture
def rag_service():
    with (
        patch("app.services.rag_service.EmbeddingService") as mock_embedding,
        patch("app.services.rag_service.VectorStoreService") as mock_store,
        patch("app.services.rag_service.chunk_document") as mock_split,
        patch(
            "app.services.rag_service.AnswerabilityService"
        ) as mock_answerability,
    ):
        mock_answerability.return_value.evaluate = AsyncMock(
            return_value=AnswerabilityResult(
                is_answerable=True,
                reason="Mocked answerability result",
            )
        )

        embedding_instance = MagicMock()
        embedding_instance.embed_documents = AsyncMock(
            return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        )
        embedding_instance.embed_query = AsyncMock(
            return_value=[0.7, 0.8, 0.9]
        )

        store_instance = MagicMock()
        store_instance.embedding_model = "test-embedding-model"
        store_instance.get_document_metadata.return_value = None
        store_instance.find_document_by_content_hash.return_value = None
        store_instance.get_embeddings_by_chunk_hash.return_value = {}
        store_instance.keyword_search.return_value = []
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
        mock_split.return_value = [Chunk("Chunk 1"), Chunk("Chunk 2")]

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
        "status": "indexed",
        "chunks_indexed": 2,
        "chunks_embedded": 2,
        "source": "api",
        "doc_type": "text",
        "visibility": "shared",
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
        where={"visibility": "shared"},
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

@pytest.mark.asyncio
async def test_index_document_cleans_up_stale_chunks(rag_service):
    service, embedding, store, split = rag_service

    result = await service.index_document(
        text="Updated document content",
        document_id="doc1",
    )

    store.delete_stale_chunks.assert_called_once_with(
        document_id="doc1",
        keep_chunk_count=2,
    )
    assert result["chunks_indexed"] == 2


@pytest.mark.asyncio
async def test_index_document_cleans_up_after_adding_chunks(rag_service):
    service, embedding, store, split = rag_service

    service.vector_store.add_chunks.side_effect = None
    call_order = []

    def mock_add_chunks(**kwargs):
        call_order.append("add")

    def mock_delete_stale_chunks(**kwargs):
        call_order.append("delete")

    store.add_chunks.side_effect = mock_add_chunks
    store.delete_stale_chunks.side_effect = mock_delete_stale_chunks

    await service.index_document(
        text="Updated document content",
        document_id="doc1",
    )

    assert call_order == ["add", "delete"]


@pytest.mark.asyncio
async def test_index_document_does_not_clean_up_if_adding_chunks_fails(rag_service):
    service, embedding, store, split = rag_service

    store.add_chunks.side_effect = RuntimeError("Vector store unavailable")

    with pytest.raises(RuntimeError, match="Vector store unavailable"):
        await service.index_document(
            text="Updated document content",
            document_id="doc1",
        )

    store.delete_stale_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_index_document_deletes_existing_chunks_when_split_is_empty(
    rag_service,
):
    service, embedding, store, split = rag_service
    split.return_value = []

    result = await service.index_document(
        text="Document content that produces no chunks",
        document_id="doc1",
    )

    assert result["chunks_indexed"] == 0
    store.delete.assert_called_once_with(document_id="doc1")
    embedding.embed_documents.assert_not_awaited()
    store.add_chunks.assert_not_called()

@pytest.mark.asyncio
async def test_index_document_preserves_existing_chunks_if_embedding_fails(
    rag_service,
):
    service, embedding, store, split = rag_service

    embedding.embed_documents.side_effect = RuntimeError(
        "Embedding service unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="Embedding service unavailable",
    ):
        await service.index_document(
            text="Updated document content",
            document_id="doc1",
        )

    store.add_chunks.assert_not_called()
    store.delete_stale_chunks.assert_not_called()
    store.delete.assert_not_called()

@pytest.mark.asyncio
async def test_index_document_does_not_delete_stale_chunks_if_upsert_fails(
    rag_service,
):
    service, embedding, store, split = rag_service

    store.add_chunks.side_effect = RuntimeError(
        "Vector store unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="Vector store unavailable",
    ):
        await service.index_document(
            text="Updated document content",
            document_id="doc1",
        )

    store.add_chunks.assert_called_once()
    store.delete_stale_chunks.assert_not_called()
    store.delete.assert_not_called()