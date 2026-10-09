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