import pytest

from app.services.keyword_index import (
    BM25Index,
    reciprocal_rank_fusion,
    tokenize,
)
from app.services.rag_service import build_search_filter, unique_results
from app.services.vector_store_service import VectorStoreService


def test_tokenize_lowercases_drops_stopwords_and_keeps_identifiers():
    assert tokenize("What is the HTTP_TIMEOUT for v1.2 in app-config?") == [
        "http_timeout",
        "v1.2",
        "app-config",
    ]


def test_bm25_ranks_rare_exact_terms_above_common_ones():
    index = BM25Index(
        ids=["a", "b", "c"],
        texts=[
            "The server returns error ERR_TOKEN_EXPIRED when a token expires.",
            "The server handles requests.",
            "The server logs requests.",
        ],
    )

    scores = index.scores("ERR_TOKEN_EXPIRED server")

    assert max(scores, key=scores.get) == "a"
    assert set(scores) == {"a", "b", "c"}
    assert index.scores("kubernetes") == {}
    assert index.scores("the of and") == {}


def test_reciprocal_rank_fusion_rewards_agreement_and_merges_fields():
    vector = [
        {"id": "a", "text": "A", "distance": 0.1},
        {"id": "b", "text": "B", "distance": 0.2},
    ]
    keyword = [
        {"id": "b", "text": "B", "distance": None, "keyword_score": 3.0},
        {"id": "c", "text": "C", "distance": None, "keyword_score": 2.0},
    ]

    fused = reciprocal_rank_fusion([vector, keyword], k=60)

    assert [result["id"] for result in fused] == ["b", "a", "c"]
    assert fused[0]["distance"] == 0.2
    assert fused[0]["keyword_score"] == 3.0
    assert fused[0]["fusion_score"] == pytest.approx(1 / 62 + 1 / 61)


def test_unique_results_keeps_best_ranked_copy_of_identical_text():
    results = [
        {"id": "a_0", "text": "Same paragraph.", "metadata": {}},
        {"id": "b_3", "text": "Same paragraph.", "metadata": {}},
        {"id": "c_0", "text": "Different.", "metadata": {}},
    ]

    assert [r["id"] for r in unique_results(results)] == ["a_0", "c_0"]


@pytest.fixture
def store(tmp_path):
    return VectorStoreService(
        persist_directory=str(tmp_path / "chroma"),
        collection_name="keyword_test",
        embedding_model="test-model",
    )


def add(store, chunk_id, text, **metadata):
    store.add_chunks(
        chunks=[text],
        embeddings=[[1.0, 0.0, 0.0]],
        ids=[chunk_id],
        metadatas=[
            {
                "document_id": chunk_id,
                "chunk_index": 0,
                "visibility": "shared",
                "owner_id": "",
                **metadata,
            }
        ],
    )


def test_keyword_search_applies_access_filter(store):
    add(store, "shared", "Rotate the JWT_SECRET_KEY yearly.")
    add(
        store,
        "secret",
        "My JWT_SECRET_KEY is hunter2.",
        visibility="private",
        owner_id="bob",
    )

    alice = store.keyword_search(
        "JWT_SECRET_KEY", where=build_search_filter(user_id="alice")
    )
    bob = store.keyword_search(
        "JWT_SECRET_KEY", where=build_search_filter(user_id="bob")
    )

    assert [result["id"] for result in alice] == ["shared"]
    assert {result["id"] for result in bob} == {"shared", "secret"}
    assert alice[0]["distance"] is None
    assert alice[0]["keyword_score"] > 0


def test_keyword_index_sees_writes_and_deletes(store):
    add(store, "one", "Original content about caching.")
    assert store.keyword_search("caching")

    add(store, "two", "New content about sharding.")
    assert [r["id"] for r in store.keyword_search("sharding")] == ["two"]

    store.delete("two")
    assert store.keyword_search("sharding") == []


@pytest.mark.asyncio
async def test_hybrid_retrieval_finds_exact_terms_vector_search_misses(
    isolated_rag_service,
):
    service = isolated_rag_service
    await service.index_document(
        "Error ERR_QUOTA_429 means the daily quota is exhausted.", "errors"
    )
    await service.index_document("General product overview.", "overview")
    # The query vector is orthogonal to every chunk, so no vector result
    # passes the distance threshold.
    service.embedding_service.embed_query.return_value = [0.0, 1.0, 0.0]

    service.hybrid_search = False
    vector_only = await service.retrieve("ERR_QUOTA_429")

    service.hybrid_search = True
    hybrid = await service.retrieve("ERR_QUOTA_429")

    assert vector_only == []
    assert [result["metadata"]["document_id"] for result in hybrid] == ["errors"]
    assert hybrid[0]["distance"] is None


@pytest.mark.asyncio
async def test_hybrid_retrieval_falls_back_to_vector_results_on_keyword_failure(
    isolated_rag_service, monkeypatch
):
    service = isolated_rag_service
    await service.index_document("FastAPI builds APIs.", "fastapi")

    def broken(**kwargs):
        raise RuntimeError("index corrupted")

    monkeypatch.setattr(service.vector_store, "keyword_search", broken)

    results = await service.retrieve("FastAPI")

    assert [result["metadata"]["document_id"] for result in results] == ["fastapi"]


@pytest.mark.asyncio
async def test_hybrid_retrieval_deduplicates_identical_chunks_across_documents(
    isolated_rag_service,
):
    service = isolated_rag_service
    footer = "Contact support at support@example.com for help."

    for document_id in ("billing", "returns"):
        add(service.vector_store, f"{document_id}_1", footer, chunk_hash="footer")

    results = await service.retrieve("support help", top_k=10)

    assert [result["text"] for result in results] == [footer]
