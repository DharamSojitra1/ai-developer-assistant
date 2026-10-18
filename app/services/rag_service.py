import asyncio
import logging
from dataclasses import dataclass
from uuid import uuid4

from app.config import (
    ENABLE_RERANKER,
    RAG_DISTANCE_THRESHOLD,
    RAG_FINAL_TOP_K,
    RAG_HYBRID_SEARCH,
    RAG_KEYWORD_TOP_K,
    RAG_RETRIEVAL_TOP_K,
    RAG_RRF_K,
    RERANKER_SCORE_THRESHOLD,
)
from app.guards.injection import screen_input
from app.services.answerability_service import AnswerabilityService
from app.services.document_service import (
    Chunk,
    chunk_document,
    chunking_signature,
)
from app.services.embedding_service import EmbeddingService
from app.services.keyword_index import reciprocal_rank_fusion
from app.services.ingestion_service import (
    DOCUMENT_TYPES,
    DocumentType,
    clean_text,
    normalize_source,
)
from app.services.reranker_service import RerankerService
from app.services.vector_store_service import (
    VISIBILITY_PRIVATE,
    VISIBILITY_SHARED,
    VectorStoreService,
)
from app.utils.hashing import text_hash

logger = logging.getLogger(__name__)

VISIBILITIES = (VISIBILITY_SHARED, VISIBILITY_PRIVATE)


class DocumentPermissionError(Exception):
    pass


class DuplicateDocumentError(Exception):
    def __init__(self, existing_document_id: str):
        super().__init__(
            f"Identical content is already indexed as document '{existing_document_id}'"
        )
        self.existing_document_id = existing_document_id


@dataclass(frozen=True)
class Requester:
    user_id: str
    is_admin: bool = False

    @classmethod
    def from_user(cls, user: dict) -> "Requester":
        return cls(
            user_id=user["user_id"],
            is_admin=user.get("role") == "admin",
        )


def build_search_filter(
    user_id: str | None = None,
    source: str | None = None,
    doc_type: str | None = None,
) -> dict:
    """Chroma `where` filter: shared documents plus the user's own private ones."""
    if user_id is None:
        access = {"visibility": VISIBILITY_SHARED}
    else:
        access = {
            "$or": [
                {"visibility": VISIBILITY_SHARED},
                {
                    "$and": [
                        {"visibility": VISIBILITY_PRIVATE},
                        {"owner_id": user_id},
                    ]
                },
            ]
        }

    conditions = [access]

    if source is not None:
        conditions.append({"source": source})

    if doc_type is not None:
        conditions.append({"doc_type": doc_type})

    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def can_modify(
    metadata: dict,
    requester: Requester,
    *,
    admin_override: bool,
) -> bool:
    if metadata.get("visibility", VISIBILITY_SHARED) == VISIBILITY_SHARED:
        return requester.is_admin

    if metadata.get("owner_id") == requester.user_id:
        return True

    return admin_override and requester.is_admin


def unique_results(results: list[dict]) -> list[dict]:
    """Keeps the best-ranked copy of chunks with identical text across documents."""
    seen = set()
    unique = []

    for result in results:
        key = (result.get("metadata") or {}).get("chunk_hash") or text_hash(
            result["text"]
        )

        if key not in seen:
            seen.add(key)
            unique.append(result)

    return unique


class RAGService:
    def __init__(
        self,
        hybrid_search: bool = RAG_HYBRID_SEARCH,
        enable_reranker: bool = ENABLE_RERANKER,
    ):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()
        self.enable_reranker = enable_reranker
        self.reranker_service = (
            RerankerService() if enable_reranker else None
        )
        self.answerability_service = AnswerabilityService()
        self.hybrid_search = hybrid_search

    async def index_document(
        self,
        text: str,
        document_id: str | None = None,
        *,
        source: str = "api",
        doc_type: DocumentType = "text",
        visibility: str = VISIBILITY_SHARED,
        requester: Requester | None = None,
    ) -> dict:
        """Clean, chunk, embed, and store a document.

        Without a `requester` the caller is trusted (scripts, tests) and no
        ownership checks are made.
        """
        if not text.strip():
            raise ValueError("Document text cannot be empty")

        if doc_type not in DOCUMENT_TYPES:
            raise ValueError(f"Unsupported document type: {doc_type}")

        if visibility not in VISIBILITIES:
            raise ValueError(f"Unsupported visibility: {visibility}")

        if visibility == VISIBILITY_PRIVATE and requester is None:
            raise ValueError("Private documents need an owner")

        source = normalize_source(source)
        document_id = document_id or str(uuid4())
        owner_id = requester.user_id if requester else ""

        existing = self._authorize_write(document_id, visibility, requester)

        text = clean_text(text, doc_type)

        if not text:
            raise ValueError("Document contains no extractable text")

        # Flag-only: the document is still indexed, and retrieval flags the
        # affected chunks again when they are used.
        screen_input(text, "indexed_document", document_id=document_id)

        result = {
            "document_id": document_id,
            "source": source,
            "doc_type": doc_type,
            "visibility": visibility,
        }

        document_metadata = {
            "document_id": document_id,
            "source": source,
            "doc_type": doc_type,
            "visibility": visibility,
            "owner_id": owner_id,
            "content_hash": text_hash(text),
            "chunking": chunking_signature(doc_type),
            "embedding_model": self.vector_store.embedding_model,
        }

        if existing is not None and all(
            existing.get(key) == value
            for key, value in document_metadata.items()
        ):
            return {
                **result,
                "status": "unchanged",
                "chunks_indexed": self.vector_store.count_chunks(document_id),
                "chunks_embedded": 0,
            }

        duplicate_id = self.vector_store.find_document_by_content_hash(
            document_metadata["content_hash"],
            where=self._duplicate_scope(visibility, requester),
            exclude_document_id=document_id,
        )

        if duplicate_id is not None:
            raise DuplicateDocumentError(duplicate_id)

        chunks = self._unique_chunks(chunk_document(text, doc_type))

        if not chunks:
            self.vector_store.delete(document_id=document_id)
            return {
                **result,
                "status": "indexed",
                "chunks_indexed": 0,
                "chunks_embedded": 0,
            }

        chunk_hashes = [text_hash(chunk.text) for chunk in chunks]

        # Identical chunk text always embeds to the same vector, so only
        # new text is sent to the embedding API.
        embeddings_by_hash = self.vector_store.get_embeddings_by_chunk_hash(
            chunk_hashes
        )
        missing = {
            chunk_hash: chunk.text
            for chunk, chunk_hash in zip(chunks, chunk_hashes)
            if chunk_hash not in embeddings_by_hash
        }

        new_embeddings = await self.embedding_service.embed_documents(
            list(missing.values())
        )
        embeddings_by_hash.update(zip(missing, new_embeddings))

        ids = [
            f"{document_id}_{i}"
            for i in range(len(chunks))
        ]

        metadatas = [
            {
                **document_metadata,
                "chunk_index": i,
                "chunk_hash": chunk_hash,
                "section": chunk.section,
            }
            for i, (chunk, chunk_hash) in enumerate(zip(chunks, chunk_hashes))
        ]

        self.vector_store.add_chunks(
            chunks=[chunk.text for chunk in chunks],
            embeddings=[embeddings_by_hash[h] for h in chunk_hashes],
            ids=ids,
            metadatas=metadatas,
        )

        self.vector_store.delete_stale_chunks(
            document_id=document_id,
            keep_chunk_count=len(chunks),
        )

        logger.info(
            "Document indexed",
            extra={
                "document_id": document_id,
                "chunks_indexed": len(chunks),
                "chunks_embedded": len(missing),
                "doc_type": doc_type,
                "visibility": visibility,
                "text_length": len(text),
            },
        )

        return {
            **result,
            "status": "indexed",
            "chunks_indexed": len(chunks),
            "chunks_embedded": len(missing),
        }

    @staticmethod
    def _unique_chunks(chunks: list[Chunk]) -> list[Chunk]:
        """Drops repeated chunks (boilerplate, repeated headers) within a document."""
        seen = set()
        unique = []

        for chunk in chunks:
            key = text_hash(chunk.text)

            if key not in seen:
                seen.add(key)
                unique.append(chunk)

        return unique

    @staticmethod
    def _duplicate_scope(
        visibility: str,
        requester: Requester | None,
    ) -> dict | None:
        # Only documents the requester can already see count as duplicates,
        # so a rejection never reveals another user's private document.
        if requester is None:
            return None

        if visibility == VISIBILITY_SHARED:
            return {"visibility": VISIBILITY_SHARED}

        return build_search_filter(user_id=requester.user_id)

    def _authorize_write(
        self,
        document_id: str,
        visibility: str,
        requester: Requester | None,
    ) -> dict | None:
        """Returns the stored document's metadata, if it already exists."""
        if (
            requester is not None
            and visibility == VISIBILITY_SHARED
            and not requester.is_admin
        ):
            raise DocumentPermissionError(
                "Only admins can add shared documents"
            )

        existing = self.vector_store.get_document_metadata(document_id)

        # Admins may delete other users' private documents, but not
        # overwrite them under their own ownership.
        if (
            requester is not None
            and existing is not None
            and not can_modify(existing, requester, admin_override=False)
        ):
            raise DocumentPermissionError(
                "You cannot modify this document"
            )

        return existing

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        *,
        user_id: str | None = None,
        source: str | None = None,
        doc_type: str | None = None,
    ) -> list[dict]:
        """Without a `user_id` only shared documents are searched."""
        if not query.strip():
            raise ValueError("Query cannot be empty")

        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        retrieval_top_k = (
            top_k if top_k is not None else RAG_RETRIEVAL_TOP_K
        )

        query_embedding = await self.embedding_service.embed_query(query)

        # Chroma and the CrossEncoder are blocking; run them in threads
        # so they don't stall the event loop and timeouts can fire.
        where = build_search_filter(
            user_id=user_id,
            source=source,
            doc_type=doc_type,
        )

        results = await asyncio.to_thread(
            self.vector_store.search,
            query_embedding=query_embedding,
            top_k=retrieval_top_k,
            where=where,
        )

        filtered_results = [
            result
            for result in results
            if result["distance"] <= RAG_DISTANCE_THRESHOLD
        ]

        if self.hybrid_search:
            keyword_results = await self._keyword_search(query, where)
            # Keyword-only matches skip the distance threshold; the reranker
            # and answerability check below still have to accept them.
            filtered_results = reciprocal_rank_fusion(
                [filtered_results, keyword_results],
                k=RAG_RRF_K,
            )[:retrieval_top_k]

        filtered_results = unique_results(filtered_results)

        if not filtered_results:
            return []

        if self.reranker_service is not None:
            try:
                reranked_results = await asyncio.to_thread(
                    self.reranker_service.rerank,
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
        else:
            score_filtered_results = filtered_results[:RAG_FINAL_TOP_K]

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

    async def _keyword_search(self, query: str, where: dict) -> list[dict]:
        try:
            return await asyncio.to_thread(
                self.vector_store.keyword_search,
                query=query,
                top_k=RAG_KEYWORD_TOP_K,
                where=where,
            )
        except Exception:
            logger.exception(
                "Keyword search failed; using vector results only",
                extra={"query_length": len(query)},
            )
            return []

    def delete_document(
        self,
        document_id: str,
        requester: Requester | None = None,
    ) -> dict:
        if not document_id.strip():
            raise ValueError("Document ID cannot be empty")

        if requester is not None:
            existing = self.vector_store.get_document_metadata(document_id)

            if existing is not None and not can_modify(
                existing, requester, admin_override=True
            ):
                raise DocumentPermissionError(
                    "You cannot delete this document"
                )

        deleted_chunks = self.vector_store.delete(document_id=document_id)    

        logger.info(
            "Document chunks deleted",
            extra={
                "document_id": document_id,
                "deleted_chunks": deleted_chunks,
            },
        )
        
        return {
            "document_id": document_id,
            "chunks_deleted": deleted_chunks,
        }
