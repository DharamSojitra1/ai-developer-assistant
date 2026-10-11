import pytest

from app.services.rag_service import RAGService
from evals.metrics import calculate_hit_rate, calculate_mrr_at_k
from evals.schema import load_rag_cases


RAG_EVALUATION_DATASET = [
    case.model_dump()
    for case in load_rag_cases()
]


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "evaluation_case",
    RAG_EVALUATION_DATASET,
    ids=[case["id"] for case in RAG_EVALUATION_DATASET],
)
async def test_rag_retrieval_evaluation(evaluation_case):
    service = RAGService()

    results = await service.retrieve(
        query=evaluation_case["query"],
        top_k=3,
    )

    if evaluation_case["expected_document_id"] is not None:
        assert results, (
            f"Expected documents for query: {evaluation_case['query']}"
        )

        document_ids = {
            result["metadata"]["document_id"]
            for result in results
        }

        assert evaluation_case["expected_document_id"] in document_ids, (
            f"Expected document {evaluation_case['expected_document_id']} "
            f"for query: {evaluation_case['query']}. "
            f"Received: {document_ids}"
        )
    else:
        assert results == [], (
            f"Expected no documents for unsupported query: "
            f"{evaluation_case['query']}. "
            f"Received: "
            f"{[result['metadata']['document_id'] for result in results]}"
        )


def test_rag_hit_rate_calculation():
    evaluation_cases = [
        {
            "query": "What is Generative AI?",
            "expected_document_id": "gen-ai-basics",
        },
        {
            "query": "What are foundation models?",
            "expected_document_id": "gen-ai-basics",
        },
        {
            "query": "What is quantum computing?",
            "expected_document_id": None,
        },
    ]

    results = [
        [
            {
                "metadata": {
                    "document_id": "gen-ai-basics",
                }
            }
        ],
        [
            {
                "metadata": {
                    "document_id": "gen-ai-basics",
                }
            }
        ],
        [],
    ]

    hit_rate = calculate_hit_rate(results, evaluation_cases)

    assert hit_rate == 1.0


@pytest.mark.live
@pytest.mark.asyncio
async def test_rag_evaluation_hit_rate():
    service = RAGService()
    results = []

    for case in RAG_EVALUATION_DATASET:
        retrieved = await service.retrieve(
            query=case["query"],
            top_k=3,
        )
        results.append(retrieved)

    hit_rate = calculate_hit_rate(
        results,
        RAG_EVALUATION_DATASET,
    )

    assert hit_rate == pytest.approx(1.0)


@pytest.mark.live
@pytest.mark.asyncio
async def test_rag_negative_query_behavior():
    service = RAGService()

    negative_cases = [
        case
        for case in RAG_EVALUATION_DATASET
        if case["expected_document_id"] is None
    ]

    false_positives = []

    for case in negative_cases:
        results = await service.retrieve(
            query=case["query"],
            top_k=3,
        )

        if results:
            false_positives.append(
                {
                    "query": case["query"],
                    "returned_documents": [
                        result["metadata"]["document_id"]
                        for result in results
                    ],
                }
            )

    print(f"\nNegative queries evaluated: {len(negative_cases)}")
    print(f"False positives: {len(false_positives)}")

    for item in false_positives:
        print(f"\nQuery: {item['query']}")
        print(f"Returned documents: {item['returned_documents']}")

    assert negative_cases, "No negative queries were evaluated"

    assert not false_positives, (
        f"RAG returned documents for unsupported queries: {false_positives}"
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_rag_evaluation_mrr():
    service = RAGService()
    results = []

    for case in RAG_EVALUATION_DATASET:
        retrieved = await service.retrieve(
            query=case["query"],
            top_k=3,
        )
        results.append(retrieved)

    mrr = calculate_mrr_at_k(
        results,
        RAG_EVALUATION_DATASET,
        k=3,
    )

    print(f"\nRAG MRR@3: {mrr:.4f}")

    assert mrr == pytest.approx(1.0), (
        f"Expected MRR@3 of 1.0, got {mrr:.4f}"
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_rag_combined_evaluation_report():
    service = RAGService()
    results = []

    for case in RAG_EVALUATION_DATASET:
        retrieved = await service.retrieve(
            query=case["query"],
            top_k=3,
        )
        results.append(retrieved)

    hit_rate = calculate_hit_rate(
        results,
        RAG_EVALUATION_DATASET,
    )

    mrr = calculate_mrr_at_k(
        results,
        RAG_EVALUATION_DATASET,
        k=3,
    )

    negative_cases = [
        (result, case)
        for result, case in zip(results, RAG_EVALUATION_DATASET)
        if case["expected_document_id"] is None
    ]

    false_positives = sum(
        1
        for result, _ in negative_cases
        if result
    )

    false_positive_rate = (
        false_positives / len(negative_cases)
        if negative_cases
        else 0.0
    )

    print("\n--- RAG Evaluation Report ---")
    print(f"Total queries: {len(results)}")
    print(f"Hit Rate@3: {hit_rate:.4f}")
    print(f"MRR@3: {mrr:.4f}")
    print(f"Negative queries: {len(negative_cases)}")
    print(f"False positives: {false_positives}")
    print(f"False-positive rate: {false_positive_rate:.4f}")

    assert hit_rate == pytest.approx(1.0)
    assert mrr == pytest.approx(1.0)
    assert false_positive_rate == pytest.approx(0.0)
