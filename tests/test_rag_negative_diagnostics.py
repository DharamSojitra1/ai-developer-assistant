import pytest

from app.services.rag_service import RAGService
from app.config import (
    RAG_DISTANCE_THRESHOLD,
    RAG_RETRIEVAL_TOP_K,
)


@pytest.mark.asyncio
async def test_inspect_negative_query_relevance():
    service = RAGService()

    
    queries = [
        "What is the history of quantum computing?",
        "How do I configure a quantum processor using FastAPI?",
        "What is FastAPI?",
        "Which framework provides automatic OpenAPI documentation and async API handling?",
        "What is Python?",
        "What is Generative AI?",
        "What are foundation models?",
        "How can I use Generative AI to compose a song?",
    ]


    for query in queries:
        embedding = await service.embedding_service.embed_query(query)

        candidates = service.vector_store.search(
            query_embedding=embedding,
            top_k=RAG_RETRIEVAL_TOP_K,
        )

        filtered = [
            document
            for document in candidates
            if document["distance"] <= RAG_DISTANCE_THRESHOLD
        ]

        print(f"\nQuery: {query}")
        print(f"Threshold: {RAG_DISTANCE_THRESHOLD}")
        print("Vector candidates:")

        for document in candidates:
            print(
                f"  ID={document['metadata']['document_id']}, "
                f"distance={document['distance']:.4f}, "
                f"passes_threshold="
                f"{document['distance'] <= RAG_DISTANCE_THRESHOLD}"
            )

        reranked = service.reranker_service.rerank(
            query=query,
            documents=filtered,
            top_k=3,
        )

        print("Reranked candidates:")

        for document in reranked:
            print(
                f"  ID={document['metadata']['document_id']}, "
                f"score={document['rerank_score']:.4f}"
            )