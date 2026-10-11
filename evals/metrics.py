"""Retrieval and latency metrics shared by the eval runner and tests.

Retrieval results are lists of documents shaped like ``RAGService.retrieve``
output (``{"metadata": {"document_id": ...}}``); evaluation cases are dicts
with an ``expected_document_id`` (None for negative queries).
"""

import math


def calculate_hit_rate(results, evaluation_cases):
    """Fraction of positive queries that retrieved the expected document."""
    hits = 0
    total_expected = 0

    for result, case in zip(results, evaluation_cases):
        expected_document_id = case["expected_document_id"]

        # Negative queries are excluded from hit-rate calculation.
        if expected_document_id is None:
            continue

        total_expected += 1

        document_ids = {
            item["metadata"]["document_id"]
            for item in result
        }

        if expected_document_id in document_ids:
            hits += 1

    if total_expected == 0:
        return 0.0

    return hits / total_expected


def calculate_mrr(results, evaluation_cases):
    reciprocal_ranks = []

    for retrieved_documents, case in zip(results, evaluation_cases):
        expected_document_id = case["expected_document_id"]

        if expected_document_id is None:
            continue

        reciprocal_rank = 0.0

        for rank, document in enumerate(retrieved_documents, start=1):
            if document["metadata"]["document_id"] == expected_document_id:
                reciprocal_rank = 1.0 / rank
                break

        reciprocal_ranks.append(reciprocal_rank)

    if not reciprocal_ranks:
        return 0.0

    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def calculate_mrr_at_k(results, evaluation_cases, k: int = 3):
    if k <= 0:
        raise ValueError("k must be greater than zero")

    limited_results = [
        retrieved_documents[:k]
        for retrieved_documents in results
    ]

    return calculate_mrr(limited_results, evaluation_cases)


def calculate_false_positive_rate(results, evaluation_cases):
    """Fraction of negative queries that retrieved anything (None if none)."""
    negative_results = [
        result
        for result, case in zip(results, evaluation_cases)
        if case["expected_document_id"] is None
    ]

    if not negative_results:
        return None

    return sum(1 for result in negative_results if result) / len(negative_results)


def percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile, e.g. fraction=0.95 for p95."""
    if not values:
        raise ValueError("values must not be empty")

    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")

    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)

    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def latency_stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None

    return {
        "mean": sum(values) / len(values),
        "p50": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
        "max": max(values),
    }
