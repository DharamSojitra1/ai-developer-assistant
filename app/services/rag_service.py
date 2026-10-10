import logging
from uuid import uuid4

from app.config import (
    RAG_DISTANCE_THRESHOLD,
    RAG_FINAL_TOP_K,
    RAG_RETRIEVAL_TOP_K,
    RERANKER_SCORE_THRESHOLD,
)
from app.services.answerability_service import AnswerabilityService
from app.services.document_service import split_document
from app.services.embedding_service import EmbeddingService
from app.services.reranker_service import RerankerService
from app.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()
        self.reranker_service = RerankerService()
        self.answerability_service = AnswerabilityService()

    async def index_document(
        self,
        text: str,
        document_id: str | None = None,
    ) -> dict:
        if not text.strip():
            raise ValueError("Document text cannot be empty")

        document_id = document_id or str(uuid4())

        chunks = split_document(text)

        if not chunks:
            return {
                "document_id": document_id,
                "chunks_indexed": 0,
            }

        embeddings = await self.embedding_service.embed_documents(chunks)

        ids = [
            f"{document_id}_{i}"
            for i in range(len(chunks))
        ]

        metadatas = [
            {
                "document_id": document_id,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        self.vector_store.add_chunks(
            chunks=chunks,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )

        return {
            "document_id": document_id,
            "chunks_indexed": len(chunks),
        }

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[dict]:
        if not query.strip():
            raise ValueError("Query cannot be empty")

        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        retrieval_top_k = (
            top_k if top_k is not None else RAG_RETRIEVAL_TOP_K
        )

        query_embedding = await self.embedding_service.embed_query(query)

        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=retrieval_top_k,
        )

        filtered_results = [
            result
            for result in results
            if result["distance"] <= RAG_DISTANCE_THRESHOLD
        ]

        if not filtered_results:
            return []

        try:
            reranked_results = self.reranker_service.rerank(
                query=query,
                documents=filtered_results,
                top_k=RAG_FINAL_TOP_K,
            )

        except Exception:
            logger.exception(
                "Reranking failed; rejecting unvalidated context",
                extra={"query_length": len(query)},
            )
            return []

        score_filtered_results = [
            document
            for document in reranked_results
            if document["rerank_score"] >= RERANKER_SCORE_THRESHOLD
        ]

        if not score_filtered_results:
            return []

        context = "\n\n".join(
            document["text"]
            for document in score_filtered_results
        )

        try:
            evaluation = await self.answerability_service.evaluate(
                query=query,
                context=context,
            )

        except Exception:
            logger.exception(
                "Answerability evaluation failed; rejecting retrieved context",
                extra={"query_length": len(query)},
            )
            return []

        if not evaluation.is_answerable:
            logger.info(
                "Retrieved context cannot answer the query",
                extra={
                    "query_length": len(query),
                    "document_count": len(score_filtered_results),
                    "reason": evaluation.reason,
                },
            )
            return []

        return score_filtered_results
