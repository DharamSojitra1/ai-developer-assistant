"""Chunk size / overlap sweep for the retrieval first stage.

    python -m evals.chunking                          # default grid
    python -m evals.chunking --sizes 400,800 --overlaps 0,0.15 --k 3

Indexes `evals/datasets/chunking/corpus/*.md` once per configuration into a
temporary Chroma collection and measures, for vector-only and hybrid search,
whether a top-k chunk contains each query's answer phrase. That checks that
chunks keep answers intact, which document-level hit rate cannot.

Costs embedding calls only (no LLM, no reranker): each distinct chunk text and
each query is embedded once across the whole sweep.
"""

import argparse
import asyncio
import json
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.config import (
    RAG_DISTANCE_THRESHOLD,
    RAG_KEYWORD_TOP_K,
    RAG_RETRIEVAL_TOP_K,
    RAG_RRF_K,
)
from app.services.document_service import chunk_document
from app.services.keyword_index import reciprocal_rank_fusion
from app.services.vector_store_service import VectorStoreService

DATASET_DIR = Path(__file__).parent / "datasets" / "chunking"
REPORTS_DIR = Path(__file__).parent / "reports"

DEFAULT_SIZES = (300, 500, 800, 1200)
DEFAULT_OVERLAPS = (0.0, 0.15)

EmbedDocuments = Callable[[list[str]], Awaitable[list[list[float]]]]
EmbedQuery = Callable[[str], Awaitable[list[float]]]


class ChunkingCase(BaseModel):
    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    tags: list[str] = []


@dataclass(frozen=True)
class ChunkingConfig:
    size: int
    overlap: int

    @property
    def label(self) -> str:
        return f"{self.size}/{self.overlap}"


def load_corpus(directory: Path = DATASET_DIR / "corpus") -> dict[str, str]:
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(directory.glob("*.md"))
    }


def load_cases(path: Path = DATASET_DIR / "queries.jsonl") -> list[ChunkingCase]:
    return [
        ChunkingCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_configs(sizes: Sequence[int], overlaps: Sequence[float]) -> list[ChunkingConfig]:
    """Overlaps below 1 are fractions of the chunk size."""
    configs = []

    for size in sizes:
        for overlap in overlaps:
            absolute = round(size * overlap) if overlap < 1 else int(overlap)

            if absolute >= size:
                raise ValueError(f"Overlap {overlap} is not smaller than size {size}")

            configs.append(ChunkingConfig(size=size, overlap=absolute))

    return configs


class CachedEmbedder:
    """Embeds each distinct text once across the sweep."""

    def __init__(self, embed_documents: EmbedDocuments, embed_query: EmbedQuery):
        self._embed_documents = embed_documents
        self._embed_query = embed_query
        self._documents: dict[str, list[float]] = {}
        self._queries: dict[str, list[float]] = {}
        self.embedded_texts = 0

    async def documents(self, texts: list[str]) -> list[list[float]]:
        missing = list(dict.fromkeys(t for t in texts if t not in self._documents))

        if missing:
            vectors = await self._embed_documents(missing)
            self._documents.update(zip(missing, vectors))
            self.embedded_texts += len(missing)

        return [self._documents[text] for text in texts]

    async def query(self, text: str) -> list[float]:
        if text not in self._queries:
            self._queries[text] = await self._embed_query(text)
            self.embedded_texts += 1

        return self._queries[text]


def answer_rank(results: list[dict], case: ChunkingCase, k: int) -> int | None:
    for rank, result in enumerate(results[:k], start=1):
        if (
            result["metadata"]["document_id"] == case.document_id
            and case.answer in result["text"]
        ):
            return rank

    return None


def _summarize(ranks: list[int | None]) -> dict:
    return {
        "hit_rate": sum(rank is not None for rank in ranks) / len(ranks),
        "mrr": sum(1 / rank for rank in ranks if rank) / len(ranks),
    }


async def evaluate_config(
    config: ChunkingConfig,
    corpus: dict[str, str],
    cases: list[ChunkingCase],
    embedder: CachedEmbedder,
    workdir: Path,
    k: int,
) -> dict:
    store = VectorStoreService(
        persist_directory=str(workdir),
        collection_name=f"sweep-{config.size}-{config.overlap}",
        embedding_model="sweep",
    )

    chunk_lengths = []

    for document_id, text in corpus.items():
        chunks = chunk_document(text, "markdown", config.size, config.overlap)
        texts = [chunk.text for chunk in chunks]
        chunk_lengths.extend(len(t) for t in texts)

        store.add_chunks(
            chunks=texts,
            embeddings=await embedder.documents(texts),
            ids=[f"{document_id}_{i}" for i in range(len(texts))],
            metadatas=[
                {"document_id": document_id, "chunk_index": i}
                for i in range(len(texts))
            ],
        )

    modes: dict[str, list[int | None]] = {"vector": [], "hybrid": []}
    per_case = []

    for case in cases:
        vector = [
            result
            for result in store.search(
                await embedder.query(case.query), top_k=RAG_RETRIEVAL_TOP_K
            )
            if result["distance"] <= RAG_DISTANCE_THRESHOLD
        ]
        keyword = store.keyword_search(case.query, top_k=RAG_KEYWORD_TOP_K)
        hybrid = reciprocal_rank_fusion([vector, keyword], k=RAG_RRF_K)

        ranks = {
            "vector": answer_rank(vector, case, k),
            "hybrid": answer_rank(hybrid, case, k),
        }

        for mode, rank in ranks.items():
            modes[mode].append(rank)

        per_case.append({"id": case.id, "tags": case.tags, **ranks})

    def by_tag(mode: str, tag: str) -> dict | None:
        ranks = [c[mode] for c in per_case if tag in c["tags"]]
        return _summarize(ranks) if ranks else None

    return {
        "size": config.size,
        "overlap": config.overlap,
        "chunks": len(chunk_lengths),
        "mean_chunk_chars": round(sum(chunk_lengths) / len(chunk_lengths)),
        **{
            mode: {
                **_summarize(ranks),
                "keyword_queries": by_tag(mode, "keyword"),
                "paraphrase_queries": by_tag(mode, "paraphrase"),
            }
            for mode, ranks in modes.items()
        },
        "cases": per_case,
    }


async def run_sweep(
    configs: list[ChunkingConfig],
    embed_documents: EmbedDocuments,
    embed_query: EmbedQuery,
    k: int = 3,
    corpus: dict[str, str] | None = None,
    cases: list[ChunkingCase] | None = None,
) -> dict:
    corpus = corpus or load_corpus()
    cases = cases or load_cases()
    embedder = CachedEmbedder(embed_documents, embed_query)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as workdir:
        results = [
            await evaluate_config(config, corpus, cases, embedder, Path(workdir), k)
            for config in configs
        ]

    return {
        "k": k,
        "documents": len(corpus),
        "queries": len(cases),
        "embedded_texts": embedder.embedded_texts,
        "results": results,
    }


def best_config(report: dict, mode: str = "hybrid") -> dict:
    # Vector-only quality breaks ties (robustness if keyword search misses),
    # then the smaller chunk wins: less context per answer, cheaper prompts.
    return max(
        report["results"],
        key=lambda r: (
            r[mode]["hit_rate"],
            r[mode]["mrr"],
            r["vector"]["hit_rate"],
            r["vector"]["mrr"],
            -r["size"],
            -r["overlap"],
        ),
    )


def format_report(report: dict) -> str:
    k = report["k"]
    lines = [
        f"Chunking sweep: {report['documents']} documents, {report['queries']} queries, "
        f"{report['embedded_texts']} texts embedded",
        "",
        f"{'size/overlap':>13} {'chunks':>6} {'avg':>5}  "
        f"{'vector hit@' + str(k):>13} {'mrr':>5}  {'hybrid hit@' + str(k):>13} {'mrr':>5}",
    ]

    for r in report["results"]:
        lines.append(
            f"{r['size']:>8}/{r['overlap']:<4} {r['chunks']:>6} {r['mean_chunk_chars']:>5}  "
            f"{r['vector']['hit_rate']:>13.2f} {r['vector']['mrr']:>5.2f}  "
            f"{r['hybrid']['hit_rate']:>13.2f} {r['hybrid']['mrr']:>5.2f}"
        )

    best = best_config(report)
    lines += ["", f"Best (hybrid): size {best['size']}, overlap {best['overlap']}"]

    return "\n".join(lines)


def _numbers(value: str, cast) -> list:
    return [cast(part) for part in value.split(",") if part.strip()]


async def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chunk size / overlap sweep.")
    parser.add_argument("--sizes", default=",".join(map(str, DEFAULT_SIZES)))
    parser.add_argument(
        "--overlaps",
        default=",".join(map(str, DEFAULT_OVERLAPS)),
        help="Fractions of the chunk size (<1) or absolute characters.",
    )
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args(argv)

    from app.services.embedding_service import EmbeddingService

    embedding_service = EmbeddingService()
    report = await run_sweep(
        build_configs(_numbers(args.sizes, int), _numbers(args.overlaps, float)),
        embedding_service.embed_documents,
        embedding_service.embed_query,
        k=args.k,
    )

    print(format_report(report))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = args.output_dir / f"chunking-{timestamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
