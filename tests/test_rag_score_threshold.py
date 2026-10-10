
import pytest

from app.services.answerability_service import AnswerabilityResult
from app.services.rag_service import RAGService


class FakeEmbeddingService:
    async def embed_query(self, query: str) -> list[float]:
        return [0.1, 0.2]


class FakeVectorStore:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
    ) -> list[dict]:
        return self.documents[:top_k]


class FakeRerankerService:
    def __init__(
        self,
        results: list[dict] | None = None,
        error: Exception | None = None,
    ):
        self.results = results or []
        self.error = error

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 3,
    ) -> list[dict]:
        if self.error is not None:
            raise self.error

        return self.results[:top_k]


class FakeAnswerabilityService:
    def __init__(self, is_answerable: bool = True):
        self.is_answerable = is_answerable

    async def evaluate(self, query: str, context: str):
        return AnswerabilityResult(
            is_answerable=self.is_answerable,
            reason="Mocked answerability result",
        )


def make_document(
    document_id: str,
    distance: float,
) -> dict:
    return {
        "id": f"{document_id}_0",
        "text": f"Content for {document_id}",
        "distance": distance,
        "metadata": {"document_id": document_id},
    }


def make_rag_service(
    documents: list[dict],
    reranker_results: list[dict] | None = None,
    reranker_error: Exception | None = None,
    is_answerable: bool = True,
) -> RAGService:
    service = RAGService.__new__(RAGService)
    service.embedding_service = FakeEmbeddingService()
    service.vector_store = FakeVectorStore(documents)
    service.reranker_service = FakeRerankerService(
        results=reranker_results,
        error=reranker_error,
    )
    service.answerability_service = FakeAnswerabilityService(
        is_answerable=is_answerable,
    )
    return service


@pytest.mark.asyncio
async def test_retrieve_filters_low_reranker_scores(monkeypatch):
    monkeypatch.setattr(
        "app.services.rag_service.RERANKER_SCORE_THRESHOLD",
        0.0,
    )

    relevant = {
        **make_document("fastapi-basics", 0.20),
        "rerank_score": 8.5,
    }
    irrelevant = {
        **make_document("quantum-basics", 0.25),
        "rerank_score": -4.1,
    }

    service = make_rag_service(
        documents=[relevant, irrelevant],
        reranker_results=[relevant, irrelevant],
    )

    results = await service.retrieve("How does FastAPI work?")

    assert len(results) == 1
    assert results[0]["metadata"]["document_id"] == "fastapi-basics"
    assert results[0]["rerank_score"] >= 0.0


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_all_scores_are_below_threshold(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.rag_service.RERANKER_SCORE_THRESHOLD",
        0.0,
    )

    irrelevant = {
        **make_document("quantum-basics", 0.25),
        "rerank_score": -4.1,
    }

    service = make_rag_service(
        documents=[irrelevant],
        reranker_results=[irrelevant],
    )

    results = await service.retrieve(
        "How do I configure a quantum processor using FastAPI?"
    )

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_reranking_fails():
    document = make_document("fastapi-basics", 0.20)

    service = make_rag_service(
        documents=[document],
        reranker_error=RuntimeError("Reranker unavailable"),
    )

    results = await service.retrieve("What is FastAPI?")

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_context_is_not_answerable():
    document = {
        **make_document("gen-ai-basics", 0.20),
        "rerank_score": 1.5,
    }

    service = make_rag_service(
        documents=[document],
        reranker_results=[document],
        is_answerable=False,
    )

    results = await service.retrieve(
        "How can I use Generative AI to compose a song?"
    )

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_returns_results_when_context_is_answerable():
    document = {
        **make_document("fastapi-basics", 0.20),
        "rerank_score": 8.5,
    }

    service = make_rag_service(
        documents=[document],
        reranker_results=[document],
        is_answerable=True,
    )

    results = await service.retrieve("What is FastAPI?")

    assert len(results) == 1
    assert results[0]["metadata"]["document_id"] == "fastapi-basics"


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_answerability_evaluation_fails():
    document = {
        **make_document("fastapi-basics", 0.20),
        "rerank_score": 8.5,
    }

    service = make_rag_service(
        documents=[document],
        reranker_results=[document],
    )

    class FailingAnswerabilityService:
        async def evaluate(self, query: str, context: str):
            raise RuntimeError("Evaluator unavailable")

    service.answerability_service = FailingAnswerabilityService()

    results = await service.retrieve("What is FastAPI?")

    assert results == []
