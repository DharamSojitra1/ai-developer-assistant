from unittest.mock import AsyncMock

import chromadb
import pytest

from app.services.embedding_migration import (
    drop_stale_collections,
    migrate_embeddings,
    pending_chunk_count,
)
from app.services.vector_store_service import (
    VectorStoreService,
    collection_name_for,
)
from app.utils.hashing import text_hash


def test_each_embedding_model_gets_its_own_collection(tmp_path):
    path = str(tmp_path / "chroma")
    old = VectorStoreService(persist_directory=path, embedding_model="model-a")
    new = VectorStoreService(persist_directory=path, embedding_model="models/b:v2")

    assert old.collection_name == "documents-model-a"
    assert new.collection_name == collection_name_for("models/b:v2")
    assert new.collection_name == "documents-models-b-v2"
    assert new.collection.metadata["embedding_model"] == "models/b:v2"


def seed(store: VectorStoreService, count: int = 3) -> None:
    store.add_chunks(
        chunks=[f"Chunk {i}" for i in range(count)],
        embeddings=[[1.0, float(i), 0.0] for i in range(count)],
        ids=[f"doc_{i}" for i in range(count)],
        metadatas=[
            {
                "document_id": "doc",
                "chunk_index": i,
                "visibility": "shared",
                "owner_id": "",
                "chunk_hash": text_hash(f"Chunk {i}"),
                "embedding_model": store.embedding_model,
            }
            for i in range(count)
        ],
    )


def fake_embedder(dimension: int = 4) -> AsyncMock:
    return AsyncMock(
        side_effect=lambda texts: [[0.5] * dimension for _ in texts]
    )


@pytest.mark.asyncio
async def test_model_change_reembeds_chunks_into_the_new_collection(tmp_path):
    path = str(tmp_path / "chroma")
    seed(VectorStoreService(persist_directory=path, embedding_model="model-a"))
    target = VectorStoreService(persist_directory=path, embedding_model="model-b")
    embed = fake_embedder(dimension=4)

    assert pending_chunk_count(target) == 3

    report = await migrate_embeddings(target, embed, batch_size=2)

    assert report.reembedded == 3
    assert report.copied == 0
    assert embed.await_count == 2
    stored = target.collection.get(include=["embeddings", "metadatas", "documents"])
    assert sorted(stored["documents"]) == ["Chunk 0", "Chunk 1", "Chunk 2"]
    assert all(len(vector) == 4 for vector in stored["embeddings"])
    assert {m["embedding_model"] for m in stored["metadatas"]} == {"model-b"}
    assert {m["visibility"] for m in stored["metadatas"]} == {"shared"}
    assert pending_chunk_count(target) == 0


@pytest.mark.asyncio
async def test_same_model_copies_vectors_without_embedding_calls(tmp_path):
    path = str(tmp_path / "chroma")
    client = chromadb.PersistentClient(path=path)
    # Pre-versioning collection: no embedding_model in its metadata.
    legacy = client.get_or_create_collection(
        "documents", metadata={"hnsw:space": "cosine"}
    )
    legacy.add(
        ids=["old_0"],
        documents=["Legacy chunk"],
        embeddings=[[0.1, 0.2, 0.3]],
        metadatas=[{"document_id": "old", "chunk_index": 0}],
    )
    target = VectorStoreService(
        persist_directory=path, embedding_model="gemini-embedding-001"
    )
    embed = fake_embedder()

    report = await migrate_embeddings(target, embed)

    embed.assert_not_awaited()
    assert report.copied == 1
    stored = target.collection.get(ids=["old_0"], include=["embeddings", "metadatas"])
    assert stored["embeddings"][0] == pytest.approx([0.1, 0.2, 0.3])
    assert stored["metadatas"][0]["chunk_hash"] == text_hash("Legacy chunk")
    assert stored["metadatas"][0]["embedding_model"] == "gemini-embedding-001"


@pytest.mark.asyncio
async def test_chunks_already_in_the_target_are_not_overwritten(tmp_path):
    path = str(tmp_path / "chroma")
    seed(VectorStoreService(persist_directory=path, embedding_model="model-a"))
    target = VectorStoreService(persist_directory=path, embedding_model="model-b")
    target.add_chunks(
        chunks=["Re-indexed chunk 0"],
        embeddings=[[9.0, 9.0, 9.0, 9.0]],
        ids=["doc_0"],
        metadatas=[{"document_id": "doc", "chunk_index": 0}],
    )

    report = await migrate_embeddings(target, fake_embedder())

    assert report.collections[0].skipped == 1
    assert report.reembedded == 2
    assert target.collection.get(ids=["doc_0"])["documents"] == ["Re-indexed chunk 0"]


@pytest.mark.asyncio
async def test_dry_run_writes_nothing_and_drop_old_removes_collections(tmp_path):
    path = str(tmp_path / "chroma")
    seed(VectorStoreService(persist_directory=path, embedding_model="model-a"))
    target = VectorStoreService(persist_directory=path, embedding_model="model-b")
    embed = fake_embedder()

    dry = await migrate_embeddings(target, embed, dry_run=True)

    assert dry.reembedded == 3
    embed.assert_not_awaited()
    assert target.collection.count() == 0

    await migrate_embeddings(target, embed)
    dropped = drop_stale_collections(target)

    assert dropped == ["documents-model-a"]
    assert [c.name for c in target.client.list_collections()] == [
        "documents-model-b"
    ]


@pytest.mark.asyncio
async def test_new_model_search_ignores_old_vectors_until_migrated(
    tmp_path,
):
    path = str(tmp_path / "chroma")
    seed(VectorStoreService(persist_directory=path, embedding_model="model-a"))
    target = VectorStoreService(persist_directory=path, embedding_model="model-b")

    # Different dimensions cannot share a collection, so the new model's
    # collection is empty rather than mixing incompatible vectors.
    assert target.search([0.5, 0.5, 0.5, 0.5], top_k=3) == []
