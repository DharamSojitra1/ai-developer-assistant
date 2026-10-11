import logging
import math
import os
import re
import threading

import chromadb

from app.config import EMBEDDING_MODEL_NAME
from app.services.keyword_index import BM25Index
from app.utils.hashing import text_hash

logger = logging.getLogger(__name__)

VISIBILITY_SHARED = "shared"
VISIBILITY_PRIVATE = "private"

COLLECTION_PREFIX = "documents"

# The collection used before embedding versioning; it was always embedded
# with this model.
LEGACY_COLLECTION_NAME = "documents"
LEGACY_EMBEDDING_MODEL = "gemini-embedding-001"

# Chunks indexed before access metadata existed were all admin-indexed,
# shared knowledge-base content.
LEGACY_CHUNK_METADATA = {
    "visibility": VISIBILITY_SHARED,
    "owner_id": "",
    "source": "api",
    "doc_type": "text",
}

# Most keyword matches considered before access filtering is applied.
MAX_KEYWORD_CANDIDATES = 1000

_backfilled_collections: set[tuple[str, str]] = set()
_backfill_lock = threading.Lock()

# Bumped on every write so cached keyword indexes are rebuilt. Writes from
# other processes are caught by the chunk-count check.
_revisions: dict[tuple[str, str], int] = {}
_keyword_indexes: dict[tuple[str, str], tuple[int, int, BM25Index]] = {}
_keyword_lock = threading.Lock()


def collection_name_for(embedding_model: str) -> str:
    """Vector dimensions are fixed per collection, so each model gets its own."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", embedding_model).strip("-._")
    return f"{COLLECTION_PREFIX}-{slug}"


class VectorStoreService:
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str | None = None,
        embedding_model: str = EMBEDDING_MODEL_NAME,
    ):
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )
        self.embedding_model = embedding_model
        self.collection_name = (
            collection_name or collection_name_for(embedding_model)
        )

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedding_model,
            },
        )

        self._key = (os.path.abspath(persist_directory), self.collection_name)
        self._backfill_legacy_metadata()

    def _changed(self) -> None:
        _revisions[self._key] = _revisions.get(self._key, 0) + 1

    def _backfill_legacy_metadata(self) -> None:
        # Access filters only match chunks that carry `visibility`, so older
        # chunks would silently disappear from every search without this.
        with _backfill_lock:
            if self._key in _backfilled_collections:
                return

            existing = self.collection.get(include=["documents", "metadatas"])

            ids = []
            metadatas = []

            for chunk_id, document, metadata in zip(
                existing["ids"],
                existing["documents"],
                existing["metadatas"],
            ):
                metadata = metadata or {}

                if "visibility" in metadata and "chunk_hash" in metadata:
                    continue

                ids.append(chunk_id)
                metadatas.append(
                    {
                        **LEGACY_CHUNK_METADATA,
                        "chunk_hash": text_hash(document or ""),
                        "embedding_model": self.embedding_model,
                        **metadata,
                    }
                )

            if ids:
                self.collection.update(ids=ids, metadatas=metadatas)
                self._changed()
                logger.info(
                    "Backfilled metadata on legacy chunks",
                    extra={"chunk_count": len(ids)},
                )

            _backfilled_collections.add(self._key)

    def add_chunks(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        ids: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        if not chunks:
            return

        if not (
            len(chunks) == len(embeddings) == len(ids)
        ):
            raise ValueError(
                "Chunks, embeddings, and IDs must have equal lengths"
            )
        if metadatas is not None and len(metadatas) != len(chunks):
            raise ValueError("Chunks and metadatas must have equal lengths")

        if any(not embedding for embedding in embeddings):
            raise ValueError("Embeddings cannot be empty")

        embedding_dimension = len(embeddings[0])

        if any(len(embedding) != embedding_dimension for embedding in embeddings):
            raise ValueError("All embeddings must have the same dimension")

        if any(
            not math.isfinite(value)
            for embedding in embeddings
            for value in embedding
        ):
            raise ValueError("Embeddings must contain only finite values")

        self.collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        self._changed()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        where: dict | None = None,
    ) -> list[dict]:
        if not query_embedding:
            raise ValueError(
                "Query embedding cannot be empty"
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero"
            )

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )

        documents = results["documents"][0]
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]

        return [
            {
                "id": ids[i],
                "text": documents[i],
                "distance": distances[i],
                "metadata": metadatas[i],
            }
            for i in range(len(documents))
        ]

    def keyword_search(
        self,
        query: str,
        top_k: int = 10,
        where: dict | None = None,
    ) -> list[dict]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        scores = self._keyword_index().scores(query)

        if not scores:
            return []

        candidates = sorted(scores, key=scores.get, reverse=True)
        candidates = candidates[:MAX_KEYWORD_CANDIDATES]

        # Chroma applies the access filter to the candidate IDs.
        allowed = self.collection.get(
            ids=candidates,
            where=where,
            include=["documents", "metadatas"],
        )

        results = [
            {
                "id": chunk_id,
                "text": document,
                "distance": None,
                "keyword_score": scores[chunk_id],
                "metadata": metadata,
            }
            for chunk_id, document, metadata in zip(
                allowed["ids"],
                allowed["documents"],
                allowed["metadatas"],
            )
        ]
        results.sort(key=lambda result: result["keyword_score"], reverse=True)

        return results[:top_k]

    def _keyword_index(self) -> BM25Index:
        with _keyword_lock:
            revision = _revisions.get(self._key, 0)
            count = self.collection.count()
            cached = _keyword_indexes.get(self._key)

            if cached and cached[0] == revision and cached[1] == count:
                return cached[2]

            existing = self.collection.get(include=["documents"])
            index = BM25Index(
                ids=existing["ids"],
                texts=[document or "" for document in existing["documents"]],
            )
            _keyword_indexes[self._key] = (revision, count, index)

            return index

    def get_document_metadata(self, document_id: str) -> dict | None:
        """Metadata of one chunk of the document, or None if it isn't stored."""
        if not document_id.strip():
            raise ValueError("Document ID cannot be empty")

        existing = self.collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
            limit=1,
        )

        if not existing["ids"]:
            return None

        return existing["metadatas"][0] or {}

    def count_chunks(self, document_id: str) -> int:
        existing = self.collection.get(
            where={"document_id": document_id},
            include=[],
        )
        return len(existing["ids"])

    def find_document_by_content_hash(
        self,
        content_hash: str,
        where: dict | None = None,
        exclude_document_id: str | None = None,
    ) -> str | None:
        """ID of another stored document with this content hash, if any."""
        conditions = [{"content_hash": content_hash}]

        if exclude_document_id is not None:
            conditions.append({"document_id": {"$ne": exclude_document_id}})

        if where:
            conditions.append(where)

        existing = self.collection.get(
            where=conditions[0] if len(conditions) == 1 else {"$and": conditions},
            include=["metadatas"],
            limit=1,
        )

        if not existing["ids"]:
            return None

        return existing["metadatas"][0].get("document_id")

    def get_embeddings_by_chunk_hash(
        self,
        chunk_hashes: list[str],
    ) -> dict[str, list[float]]:
        """Stored embeddings for chunks whose text hashes match, to skip re-embedding."""
        if not chunk_hashes:
            return {}

        existing = self.collection.get(
            where={"chunk_hash": {"$in": sorted(set(chunk_hashes))}},
            include=["embeddings", "metadatas"],
        )

        return {
            metadata["chunk_hash"]: [float(value) for value in embedding]
            for embedding, metadata in zip(
                existing["embeddings"],
                existing["metadatas"],
            )
            if metadata and metadata.get("chunk_hash")
        }

    def delete(self, document_id: str) -> int:
        if not document_id.strip():
            raise ValueError("Document ID cannot be empty")
        
        existing = self.collection.get(
            where = {"document_id": document_id},
            include = [],
        )

        ids = existing["ids"]

        if not ids:
            return 0

        self.collection.delete(ids=ids)
        self._changed()

        return len(ids)

    def delete_stale_chunks(self, document_id: str, keep_chunk_count: int) -> int:
        if not document_id.strip():
            raise ValueError("Document ID cannot be empty")
        
        if keep_chunk_count <= 0:
            raise ValueError("keep_chunk_count must be greater than zero")
        
        existing = self.collection.get(
            where = {"document_id": document_id},
            include = ["metadatas"],
        )

        stale_ids = [
            chunk_id
            for chunk_id, metadata in zip(
                existing["ids"],
                existing["metadatas"],
            )
            if metadata
            and metadata.get("document_id") == document_id
            and metadata.get("chunk_index", -1) >= keep_chunk_count
        ]
        
        if stale_ids:
            self.collection.delete(ids=stale_ids)
            self._changed()

        return len(stale_ids)
