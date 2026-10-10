import pytest

from app.services.rag_service import RAGService
from app.config import (
    RAG_DISTANCE_THRESHOLD,
    RAG_RETRIEVAL_TOP_K,
    RAG_FINAL_TOP_K,
)
from tests.test_rag_evaluation import (
    RAG_EVALUATION_DATASET,
    calculate_hit_rate,
)
from tests.test_rag_mrr import calculate_mrr


@pytest.mark.asyncio
async def test_compare_rag_before_and_after_reranking():
    service = RAGService()

    baseline_results = []
    reranked_results = []

    for case in RAG_EVALUATION_DATASET:
        query = case["query"]

        query_embedding = await service.embedding_service.embed_query(
            query
        )

        candidates = service.vector_store.search(
            query_embedding=query_embedding,
            top_k=RAG_RETRIEVAL_TOP_K,
        )

        filtered_candidates = [
            document
            for document in candidates
            if document["distance"] <= RAG_DISTANCE_THRESHOLD
        ]

        baseline_results.append(
            filtered_candidates[:RAG_FINAL_TOP_K]
        )

        try:
            reranked = service.reranker_service.rerank(
                query=query,
                documents=filtered_candidates,
                top_k=RAG_FINAL_TOP_K,
            )
        except Exception as exc:
            pytest.fail(
                f"Reranker failed for query {query!r}: {exc}"
            )

        reranked_results.append(reranked)

    baseline_hit_rate = calculate_hit_rate(
        baseline_results,
        RAG_EVALUATION_DATASET,
    )

    reranked_hit_rate = calculate_hit_rate(
        reranked_results,
        RAG_EVALUATION_DATASET,
    )

    baseline_mrr = calculate_mrr(
        baseline_results,
        RAG_EVALUATION_DATASET,
    )

    reranked_mrr = calculate_mrr(
        reranked_results,
        RAG_EVALUATION_DATASET,
    )

    print(f"\nBaseline Hit Rate@3: {baseline_hit_rate:.4f}")
    print(f"Reranked Hit Rate@3: {reranked_hit_rate:.4f}")
    print(f"Baseline MRR@3:      {baseline_mrr:.4f}")
    print(f"Reranked MRR@3:      {reranked_mrr:.4f}")

    assert 0.0 <= baseline_hit_rate <= 1.0
    assert 0.0 <= reranked_hit_rate <= 1.0
    assert 0.0 <= baseline_mrr <= 1.0
    assert 0.0 <= reranked_mrr <= 1.0
