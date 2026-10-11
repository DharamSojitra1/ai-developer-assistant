import zlib

import pytest

from app.services.keyword_index import tokenize
from evals.chunking import (
    best_config,
    build_configs,
    format_report,
    load_cases,
    load_corpus,
    run_sweep,
)


def test_every_answer_phrase_appears_verbatim_in_its_document():
    corpus = load_corpus()
    cases = load_cases()

    assert len(corpus) >= 4
    assert len({case.id for case in cases}) == len(cases)

    for case in cases:
        assert case.document_id in corpus, case.id
        assert case.answer in corpus[case.document_id], case.id


def test_build_configs_accepts_fractions_and_absolute_overlaps():
    configs = build_configs([400, 800], [0, 0.25, 50])

    assert [c.label for c in configs] == [
        "400/0", "400/100", "400/50", "800/0", "800/200", "800/50",
    ]

    with pytest.raises(ValueError):
        build_configs([100], [100])


def bag_of_words(text: str, dimension: int = 256) -> list[float]:
    vector = [0.0] * dimension

    for token in tokenize(text):
        vector[zlib.crc32(token.encode()) % dimension] += 1.0

    return vector if any(vector) else [1.0] + [0.0] * (dimension - 1)


@pytest.mark.asyncio
async def test_sweep_runs_offline_and_reports_every_config():
    calls = []

    async def embed_documents(texts):
        calls.append(len(texts))
        return [bag_of_words(text) for text in texts]

    async def embed_query(text):
        return bag_of_words(text)

    configs = build_configs([300, 800], [0, 0.15])
    report = await run_sweep(configs, embed_documents, embed_query, k=3)

    assert [(r["size"], r["overlap"]) for r in report["results"]] == [
        (300, 0), (300, 45), (800, 0), (800, 120),
    ]
    for result in report["results"]:
        assert 0 <= result["hybrid"]["hit_rate"] <= 1
        assert result["hybrid"]["keyword_queries"] is not None
        assert len(result["cases"]) == report["queries"]

    # Keyword queries name exact identifiers, which BM25 finds directly.
    assert all(
        r["hybrid"]["keyword_queries"]["hit_rate"] == 1.0
        for r in report["results"]
    )
    # Each distinct text is embedded once across the whole sweep.
    assert report["embedded_texts"] == sum(calls) + report["queries"]
    assert best_config(report) in report["results"]
    assert "Best (hybrid)" in format_report(report)
