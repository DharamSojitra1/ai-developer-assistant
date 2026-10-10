from app.services.reranker_service import RerankerService


def test_reranker_ranks_relevant_document_higher():
    service = RerankerService()

    results = service.rerank(
        query="What is FastAPI?",
        documents=[
            {
                "id": "python",
                "text": (
                    "Python is a high-level programming language "
                    "used for software development."
                ),
            },
            {
                "id": "fastapi",
                "text": (
                    "FastAPI is a modern Python web framework "
                    "for building APIs."
                ),
            },
            {
                "id": "quantum",
                "text": (
                    "Quantum computing uses quantum mechanical "
                    "phenomena to perform computations."
                ),
            },
        ],
        top_k=3,
    )

    assert len(results) == 3

    assert results[0]["id"] == "fastapi"

    assert "rerank_score" in results[0]
    assert "rerank_score" in results[1]
    assert "rerank_score" in results[2]

    assert results[0]["rerank_score"] > results[1]["rerank_score"]
    assert results[0]["rerank_score"] > results[2]["rerank_score"]

def test_inspect_reranker_scores():
    service = RerankerService()

    query = "How do I configure a quantum processor using FastAPI?"

    documents = [
        {
            "id": "fastapi",
            "text": (
                "FastAPI is a modern Python web framework for "
                "building APIs. It provides automatic OpenAPI "
                "documentation and asynchronous request handling."
            ),
        },
        {
            "id": "quantum",
            "text": (
                "Quantum computing uses quantum mechanical "
                "phenomena to perform computations."
            ),
        },
    ]

    results = service.rerank(
        query=query,
        documents=documents,
        top_k=2,
    )

    for result in results:
        print(
            f"\nID: {result['id']}"
            f"\nScore: {result['rerank_score']}"
        )
