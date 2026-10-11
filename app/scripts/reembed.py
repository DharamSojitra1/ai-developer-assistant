"""Fill the active embedding collection after EMBEDDING_MODEL_NAME changes.

    python -m app.scripts.reembed --dry-run     # show what would happen
    python -m app.scripts.reembed               # copy / re-embed chunks
    python -m app.scripts.reembed --drop-old    # then delete old collections
"""

import argparse
import asyncio

from app.services.embedding_migration import (
    drop_stale_collections,
    migrate_embeddings,
)
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import VectorStoreService


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--drop-old",
        action="store_true",
        help="Delete the old collections after a successful migration.",
    )
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args(argv)

    target = VectorStoreService()
    embedding_service = EmbeddingService(model_name=target.embedding_model)

    report = await migrate_embeddings(
        target,
        embedding_service.embed_documents,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    prefix = "[dry run] " if args.dry_run else ""
    print(f"{prefix}Target: {report.target_collection} ({report.target_model})")

    if not report.collections:
        print("No older collections found; nothing to migrate.")

    for item in report.collections:
        print(
            f"{prefix}{item.collection} ({item.embedding_model}): "
            f"{item.chunks} chunks, {item.copied} copied, "
            f"{item.reembedded} re-embedded, {item.skipped} already present"
        )

    if args.drop_old and not args.dry_run:
        for name in drop_stale_collections(target):
            print(f"Dropped collection {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
