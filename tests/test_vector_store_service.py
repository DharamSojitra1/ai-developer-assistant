import pytest

from app.services.vector_store_service import VectorStoreService


@pytest.fixture
def vector_store(tmp_path):
    return VectorStoreService(
        persist_directory=str(tmp_path / "test_chroma_db"),
        collection_name="test_documents",
    )


def test_add_and_search_chunks(vector_store):
    chunks = [
        "FastAPI is a Python web framework.",
        "Python is a programming language.",
        "Solana is a blockchain platform.",
    ]

    embeddings = [
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 0.0, 1.0],
    ]

    ids = ["doc1", "doc2", "doc3"]

    vector_store.add_chunks(
        chunks=chunks,
        embeddings=embeddings,
        ids=ids,
    )

    results = vector_store.search(
        query_embedding=[1.0, 0.0, 0.0],
        top_k=2,
    )

    assert len(results) == 2
    assert results[0]["id"] == "doc1"
    assert results[0]["text"] == chunks[0]


def test_empty_chunks(vector_store):
    vector_store.add_chunks(
        chunks=[],
        embeddings=[],
        ids=[],
    )


def test_mismatched_lengths(vector_store):
    with pytest.raises(ValueError, match="equal lengths"):
        vector_store.add_chunks(
            chunks=["Chunk 1", "Chunk 2"],
            embeddings=[[0.1, 0.2, 0.3]],
            ids=["doc1"],
        )


def test_empty_query_embedding(vector_store):
    with pytest.raises(
        ValueError,
        match="Query embedding cannot be empty",
    ):
        vector_store.search(query_embedding=[])


def test_invalid_top_k(vector_store):
    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        vector_store.search(
            query_embedding=[1.0, 0.0, 0.0],
            top_k=0,
        )