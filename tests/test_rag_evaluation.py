import pytest

from app.services.rag_service import RAGService
from tests.test_rag_mrr import calculate_mrr_at_k


RAG_EVALUATION_DATASET = [
    {
        "query": "What is Generative AI?",
        "expected_document_id": "gen-ai-basics",
        "should_retrieve": True,
    },
    {
        "query": "What kind of content can Generative AI generate?",
        "expected_document_id": "gen-ai-basics",
        "should_retrieve": True,
    },
    {
        # The knowledge base mentions foundation models but does not
        # define them. This query asks about models used by Generative AI.
        "query": "What kind of models does Generative AI commonly use?",
        "expected_document_id": "gen-ai-basics",
        "should_retrieve": True,
    },
    {
        "query": "What is Python?",
        "expected_document_id": "python-basics",
        "should_retrieve": True,
    },
    {
        "query": "What is FastAPI?",
        "expected_document_id": "fastapi-basics",
        "should_retrieve": True,
    },
    {
        "query": "What is the history of quantum computing?",
        "expected_document_id": None,
        "should_retrieve": False,
    },
    {
        "query": "Which AI technology can create new text, images, audio, video, and code?",
        "expected_document_id": "gen-ai-basics",
        "should_retrieve": True,
    },
    {
        "query": "What programming language is known for readable syntax and used in AI?",
        "expected_document_id": "python-basics",
        "should_retrieve": True,
    },
    {
        "query": "Which framework provides automatic OpenAPI documentation and async API handling?",
        "expected_document_id": "fastapi-basics",
        "should_retrieve": True,
    },
    {
        "query": "Which framework is used to build APIs with Python?",
        "expected_document_id": "fastapi-basics",
        "should_retrieve": True,
    },
    {
        "query": "How do I configure a quantum processor using FastAPI?",
        "expected_document_id": None,
        "should_retrieve": False,
    },
    {
        "query": "How do I deploy a FastAPI application to Kubernetes?",
        "expected_document_id": None,
        "should_retrieve": False,
    },
    {
        "query": "How do I train a neural network for image recognition using Python?",
        "expected_document_id": None,
        "should_retrieve": False,
    },
    {
        "query": "How can I use Generative AI to compose a song?",
        "expected_document_id": None,
        "should_retrieve": False,
    },
]


def calculate_hit_rate(results, evaluation_cases):
    """Calculate the fraction of positive queries retrieving the expected document."""
    hits = 0
    total_expected = 0

    for result, case in zip(results, evaluation_cases):
        expected_document_id = case["expected_document_id"]

        # Negative queries are excluded from hit-rate calculation.
        if expected_document_id is None:
            continue

        total_expected += 1

        document_ids = {
            item["metadata"]["document_id"]
            for item in result
        }

        if expected_document_id in document_ids:
            hits += 1

    if total_expected == 0:
        return 0.0

    return hits / total_expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "evaluation_case",
    RAG_EVALUATION_DATASET,
)
async def test_rag_retrieval_evaluation(evaluation_case):
    service = RAGService()

    results = await service.retrieve(
        query=evaluation_case["query"],
        top_k=3,
    )

    if evaluation_case["should_retrieve"]:
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