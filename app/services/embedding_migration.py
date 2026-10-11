"""Re-embed stored chunks when the embedding model changes.

Each embedding model has its own collection (`collection_name_for`). After
`EMBEDDING_MODEL_NAME` changes, the new collection starts empty; this fills it
from the older collections. Chunks whose source collection already used the
target model are copied with their vectors, so only real model changes cost
embedding calls.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.services.vector_store_service import (
    COLLECTION_PREFIX,
    LEGACY_COLLECTION_NAME,
    LEGACY_EMBEDDING_MODEL,
    VectorStoreService,
)
from app.utils.hashing import text_hash

logger = logging.getLogger(__name__)

EmbedDocuments = Callable[[list[str]], Awaitable[list[list[float]]]]


@dataclass
class CollectionMigration:
    collection: str
    embedding_model: str
    chunks: int = 0
    copied: int = 0
    reembedded: int = 0
    skipped: int = 0


@dataclass
class MigrationReport:
    target_collection: str
    target_model: str
    collections: list[CollectionMigration] = field(default_factory=list)

    @property
    def reembedded(self) -> int:
        return sum(item.reembedded for item in self.collections)

    @property
    def copied(self) -> int:
        return sum(item.copied for item in self.collections)


def source_embedding_model(collection) -> str:
    metadata = collection.metadata or {}

    if metadata.get("embedding_model"):
        return metadata["embedding_model"]

    if collection.name == LEGACY_COLLECTION_NAME:
        return LEGACY_EMBEDDING_MODEL

    raise ValueError(
        f"Collection '{collection.name}' does not record its embedding model"
    )


def stale_collections(target: VectorStoreService) -> list:
    """Other document collections, i.e. ones embedded with a different model."""
    return [
        collection
        for collection in target.client.list_collections()
        if collection.name != target.collection_name
        and (
            collection.name == LEGACY_COLLECTION_NAME
            or collection.name.startswith(f"{COLLECTION_PREFIX}-")
        )
    ]


def pending_chunk_count(target: VectorStoreService) -> int:
    """Chunks in older collections that the active collection does not have."""
    present = set(target.collection.get(include=[])["ids"])

    return sum(
        len(set(collection.get(include=[])["ids"]) - present)
        for collection in stale_collections(target)
    )


async def migrate_embeddings(
    target: VectorStoreService,
    embed_documents: EmbedDocuments,
    batch_size: int = 64,
    dry_run: bool = False,
) -> MigrationReport:
    report = MigrationReport(
        target_collection=target.collection_name,
        target_model=target.embedding_model,
    )

    for collection in stale_collections(target):
        model = source_embedding_model(collection)
        same_model = model == target.embedding_model
        item = CollectionMigration(collection=collection.name, embedding_model=model)
        report.collections.append(item)

        stored = collection.get(
            include=["documents", "metadatas"]
            + (["embeddings"] if same_model else [])
        )

        if not stored["ids"]:
            continue

        existing = target.collection.get(
            ids=stored["ids"],
            include=["metadatas"],
        )
        # Chunks already in the target (e.g. re-indexed since the model
        # change) are newer than the old copies.
        already_present = set(existing["ids"])

        rows = [
            row
            for row in zip(
                stored["ids"],
                stored["documents"],
                stored["metadatas"],
                stored["embeddings"] if same_model else [None] * len(stored["ids"]),
            )
            if row[0] not in already_present
        ]
        item.chunks = len(stored["ids"])
        item.skipped = item.chunks - len(rows)

        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            ids = [row[0] for row in batch]
            texts = [row[1] or "" for row in batch]

            if same_model:
                embeddings = [[float(v) for v in row[3]] for row in batch]
                item.copied += len(batch)
            else:
                embeddings = [] if dry_run else await embed_documents(texts)
                item.reembedded += len(batch)

            if dry_run:
                continue

            metadatas = [
                {
                    **(row[2] or {}),
                    "chunk_hash": (row[2] or {}).get("chunk_hash") or text_hash(text),
                    "embedding_model": target.embedding_model,
                }
                for row, text in zip(batch, texts)
            ]

            target.add_chunks(
                chunks=texts,
                embeddings=embeddings,
                ids=ids,
                metadatas=metadatas,
            )

        logger.info(
            "Embedding migration processed collection",
            extra={
                "source_collection": collection.name,
                "source_model": model,
                "target_collection": target.collection_name,
                "copied": item.copied,
                "reembedded": item.reembedded,
                "skipped": item.skipped,
                "dry_run": dry_run,
            },
        )

    return report


def drop_stale_collections(target: VectorStoreService) -> list[str]:
    names = [collection.name for collection in stale_collections(target)]

    for name in names:
        target.client.delete_collection(name)

    return names
