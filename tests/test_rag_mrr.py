import pytest

def calculate_mrr(results, evaluation_cases):
    reciprocal_ranks = []

    for retrieved_documents, case in zip(
        results,
        evaluation_cases,
    ):
        expected_document_id = case["expected_document_id"]

        if expected_document_id is None:
            continue

        reciprocal_rank = 0.0

        for rank, document in enumerate(
            retrieved_documents,
            start=1,
        ):
            if (
                document["metadata"]["document_id"]
                == expected_document_id
            ):
                reciprocal_rank = 1.0 / rank
                break

        reciprocal_ranks.append(reciprocal_rank)

    if not reciprocal_ranks:
        return 0.0

    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def test_mrr_when_expected_documents_are_first():
    cases = [
        {"expected_document_id": "doc-a"},
        {"expected_document_id": "doc-b"},
    ]

    results = [
        [{"metadata": {"document_id": "doc-a"}}],
        [{"metadata": {"document_id": "doc-b"}}],
    ]

    assert calculate_mrr(results, cases) == 1.0


def test_mrr_when_expected_document_is_second():
    cases = [{"expected_document_id": "doc-a"}]

    results = [
        [
            {"metadata": {"document_id": "doc-b"}},
            {"metadata": {"document_id": "doc-a"}},
        ]
    ]

    assert calculate_mrr(results, cases) == 0.5


def test_mrr_when_expected_document_is_missing():
    cases = [{"expected_document_id": "doc-a"}]

    results = [
        [{"metadata": {"document_id": "doc-b"}}]
    ]

    assert calculate_mrr(results, cases) == 0.0


def test_mrr_ignores_cases_without_expected_document():
    cases = [
        {"expected_document_id": None},
        {"expected_document_id": "doc-a"},
    ]

    results = [
        [{"metadata": {"document_id": "doc-b"}}],
        [{"metadata": {"document_id": "doc-a"}}],
    ]

    assert calculate_mrr(results, cases) == 1.0


def test_mrr_returns_zero_when_no_cases_are_evaluable():
    cases = [{"expected_document_id": None}]
    results = [[]]

    assert calculate_mrr(results, cases) == 0.0


def calculate_mrr_at_k(results, evaluation_cases, k: int = 3):
    if k <= 0:
        raise ValueError("k must be greater than zero")

    limited_results = [
        retrieved_documents[:k]
        for retrieved_documents in results
    ]

    return calculate_mrr(
        limited_results,
        evaluation_cases,
    )



def test_mrr_at_k_ignores_documents_beyond_k():
    cases = [{"expected_document_id": "doc-a"}]

    results = [
        [
            {"metadata": {"document_id": "doc-b"}},
            {"metadata": {"document_id": "doc-c"}},
            {"metadata": {"document_id": "doc-a"}},
        ]
    ]

    assert calculate_mrr_at_k(results, cases, k=2) == 0.0


def test_mrr_at_k_rejects_non_positive_k():
    with pytest.raises(ValueError, match="k must be greater than zero"):
        calculate_mrr_at_k([], [], k=0)
