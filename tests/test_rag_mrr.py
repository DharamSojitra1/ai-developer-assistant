import pytest

from evals.metrics import calculate_mrr, calculate_mrr_at_k


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
