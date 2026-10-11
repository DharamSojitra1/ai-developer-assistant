
from unittest.mock import MagicMock, patch

import pytest

from app.services.vector_store_service import VectorStoreService


@pytest.fixture
def vector_store():
    with patch(
        "app.services.vector_store_service.chromadb.PersistentClient"
    ) as mock_client:
        client = mock_client.return_value
        collection = MagicMock()
        client.get_or_create_collection.return_value = collection

        service = VectorStoreService()
        yield service, collection


def test_delete_stale_chunks_removes_only_old_chunks(vector_store):
    service, collection = vector_store

    collection.get.return_value = {
        "ids": ["doc1_0", "doc1_1", "doc1_2", "doc1_3"],
        "metadatas": [
            {"document_id": "doc1", "chunk_index": 0},
            {"document_id": "doc1", "chunk_index": 1},
            {"document_id": "doc1", "chunk_index": 2},
            {"document_id": "doc1", "chunk_index": 3},
        ],
    }

    deleted = service.delete_stale_chunks("doc1", keep_chunk_count=3)

    assert deleted == 1
    collection.delete.assert_called_once_with(ids=["doc1_3"])


def test_delete_stale_chunks_returns_zero_when_none_are_stale(vector_store):
    service, collection = vector_store

    collection.get.return_value = {
        "ids": ["doc1_0", "doc1_1"],
        "metadatas": [
            {"document_id": "doc1", "chunk_index": 0},
            {"document_id": "doc1", "chunk_index": 1},
        ],
    }

    deleted = service.delete_stale_chunks("doc1", keep_chunk_count=2)

    assert deleted == 0
    collection.delete.assert_not_called()


@pytest.mark.parametrize("keep_chunk_count", [-1, 0])
def test_delete_stale_chunks_rejects_non_positive_count(
    vector_store,
    keep_chunk_count,
):
    service, collection = vector_store

    with pytest.raises(
        ValueError,
        match="keep_chunk_count must be greater than zero",
    ):
        service.delete_stale_chunks("doc1", keep_chunk_count=keep_chunk_count)

    collection.get.assert_not_called()

def test_delete_stale_chunks_preserves_other_documents(vector_store):
    service, collection = vector_store

    collection.get.return_value = {
        "ids": ["doc1_0", "doc1_3", "doc2_4"],
        "metadatas": [
            {"document_id": "doc1", "chunk_index": 0},
            {"document_id": "doc1", "chunk_index": 3},
            {"document_id": "doc2", "chunk_index": 4},
        ],
    }

    deleted = service.delete_stale_chunks(
        "doc1",
        keep_chunk_count=3,
    )

    assert deleted == 1
    collection.delete.assert_called_once_with(ids=["doc1_3"])

def test_delete_stale_chunks_rejects_zero_count(vector_store):
    service, collection = vector_store

    with pytest.raises(
        ValueError,
        match="keep_chunk_count must be greater than zero",
    ):
        service.delete_stale_chunks(
            "doc1",
            keep_chunk_count=0,
        )

    collection.get.assert_not_called()

def test_delete_document_fetches_only_ids(vector_store):
    service, collection = vector_store

    collection.get.return_value = {"ids": ["doc1_0", "doc1_1"]}

    deleted = service.delete("doc1")

    assert deleted == 2
    collection.get.assert_called_once_with(
        where={"document_id": "doc1"},
        include=[],
    )
    collection.delete.assert_called_once_with(
        ids=["doc1_0", "doc1_1"],
    )