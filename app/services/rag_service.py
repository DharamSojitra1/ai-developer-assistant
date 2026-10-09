from uuid import uuid4

from app.services.document_service import split_document
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import VectorStoreService
from app.config import RAG_DISTANCE_THRESHOLD, RAG_RETRIEVAL_TOP_K, RAG_FINAL_TOP_K
from app.services.reranker_service import RerankerService

class RAGService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()
        self.reranker_service = RerankerService()
    
    async def index_document(
        self,
        text: str,
        document_id: str | None = None,        
    ) -> dict:

        if not text.strip():
            raise ValueError("Document text cannot be empty")
        
        document_id = document_id or str(uuid4())

        chunks = split_document(text)

        embeddings = await self.embedding_service.embed_documents(chunks)

        ids = [f"{document_id}_{i}" for i in range(len(chunks))]

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
            metadatas=metadatas
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
        
        query_embedding = await self.embedding_service.embed_query(query)
        retrieval_top_k = top_k or RAG_RETRIEVAL_TOP_K

        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=retrieval_top_k
        )

        filtered_results = [
            result
            for result in results
            if result["distance"] <= RAG_DISTANCE_THRESHOLD
        ]

        reranked_results = self.reranker_service.rerank(
            query=query,
            documents=filtered_results,
            top_k=RAG_FINAL_TOP_K
        )

        return reranked_results