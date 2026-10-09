import pytest

from app.services.rag_service import RAGService


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
        "query": "What are foundation models?",
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
]


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
        assert results

        document_ids = {
            result["metadata"]["document_id"]
            for result in results
        }

        assert evaluation_case["expected_document_id"] in document_ids

    else:
        assert results == []

def calculate_hit_rate(results, evaluation_cases):
    hits = 0
    total_expected = 0

    for result, case in zip(results, evaluation_cases):
        expected_document_id = case["expected_document_id"]

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

    hit_rate = calculate_hit_rate(
        results,
        evaluation_cases,
    )

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

    assert hit_rate == 1.0

