import json

import pytest

from evals.checks import AgentRunOutcome, check_agent_case, is_refusal
from evals.schema import (
    AgentEvalCase,
    DatasetError,
    load_agent_cases,
    load_cases,
    load_rag_cases,
)


def write_jsonl(path, *rows):
    path.write_text(
        "\n".join(
            row if isinstance(row, str) else json.dumps(row)
            for row in rows
        ),
        encoding="utf-8",
    )
    return path


def make_case(**overrides) -> AgentEvalCase:
    return AgentEvalCase.model_validate(
        {"id": "case-1", "question": "Q?", **overrides}
    )


def test_shipped_datasets_are_valid():
    agent_cases = load_agent_cases()
    rag_cases = load_rag_cases()

    assert agent_cases
    assert any(case.expected_document_id is None for case in rag_cases)
    assert any(case.expected_document_id for case in rag_cases)


def test_loader_skips_blank_and_comment_lines(tmp_path):
    path = write_jsonl(
        tmp_path / "agent.jsonl",
        "# comment",
        "",
        {"id": "a", "question": "What is 1 + 1?"},
    )

    cases = load_agent_cases(path)

    assert [case.id for case in cases] == ["a"]
    assert cases[0].expected_tools == []
    assert cases[0].expected_sources is None


@pytest.mark.parametrize(
    "row, message",
    [
        ("{not json", "invalid JSON"),
        ({"id": "a"}, "question"),
        ({"id": "a", "question": "   "}, "must not be blank"),
        ({"id": "a", "question": "Q?", "extra": 1}, "extra"),
        (
            {"id": "a", "question": "Q?", "expected_tools": ["shell"]},
            "unknown tool 'shell'",
        ),
        (
            {
                "id": "a",
                "question": "Q?",
                "expected_answer": {"refusal": True, "contains": ["x"]},
            },
            "refusal cannot also require",
        ),
    ],
)
def test_loader_reports_invalid_line_with_location(tmp_path, row, message):
    path = write_jsonl(
        tmp_path / "agent.jsonl",
        {"id": "ok", "question": "Q?"},
        row,
    )

    with pytest.raises(DatasetError, match="agent.jsonl:2") as exc_info:
        load_agent_cases(path)

    assert message in str(exc_info.value)


def test_loader_rejects_duplicate_ids(tmp_path):
    path = write_jsonl(
        tmp_path / "rag.jsonl",
        {"id": "a", "query": "Q?", "expected_document_id": None},
        {"id": "a", "query": "Q2?", "expected_document_id": "doc"},
    )

    with pytest.raises(DatasetError, match="duplicate id 'a'"):
        load_rag_cases(path)


def test_loader_rejects_empty_dataset(tmp_path):
    path = write_jsonl(tmp_path / "rag.jsonl", "# only a comment")

    with pytest.raises(DatasetError, match="empty"):
        load_cases(path, AgentEvalCase)


def test_rag_case_requires_explicit_expected_document(tmp_path):
    path = write_jsonl(tmp_path / "rag.jsonl", {"id": "a", "query": "Q?"})

    with pytest.raises(DatasetError, match="expected_document_id"):
        load_rag_cases(path)


def test_check_passes_when_all_expectations_met():
    case = make_case(
        expected_tools=["calculator"],
        expected_answer={"contains": ["500"], "contains_any": ["is", "equals"]},
        expected_sources=[],
    )

    outcome = AgentRunOutcome(
        answer="125 * 4 is 500.",
        tools_called=["calculator"],
    )

    assert check_agent_case(case, outcome) == []


def test_check_reports_every_unmet_expectation():
    case = make_case(
        expected_tools=["search_knowledge_base"],
        expected_answer={"contains": ["text", "audio"], "contains_any": ["video"]},
        expected_sources=["gen-ai-basics"],
    )

    outcome = AgentRunOutcome(
        answer="It generates text.",
        tools_called=["calculator"],
        source_ids=["python-basics"],
    )

    failures = check_agent_case(case, outcome)

    assert len(failures) == 4
    assert "search_knowledge_base" in failures[0]
    assert "audio" in failures[1]
    assert "video" in failures[2]
    assert "gen-ai-basics" in failures[3]


def test_check_answer_matching_is_case_insensitive():
    case = make_case(expected_answer={"contains": ["Image"]})

    outcome = AgentRunOutcome(answer="IMAGES and text")

    assert check_agent_case(case, outcome) == []


def test_empty_expected_sources_means_no_sources_allowed():
    case = make_case(expected_sources=[])

    failures = check_agent_case(
        case,
        AgentRunOutcome(answer="x", source_ids=["gen-ai-basics"]),
    )

    assert failures == ["expected no sources, got ['gen-ai-basics']"]


def test_null_expected_sources_skips_source_check():
    case = make_case()

    outcome = AgentRunOutcome(answer="x", source_ids=["anything"])

    assert check_agent_case(case, outcome) == []


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("I\u2019m sorry, I couldn\u2019t find that.", True),
        ("The knowledge base does not have enough information.", True),
        ("Quantum computing started in the 1980s.", False),
    ],
)
def test_is_refusal(answer, expected):
    assert is_refusal(answer) is expected


@pytest.mark.parametrize(
    "answer, passes",
    [
        ("125 * 4 is 500.", True),
        ("The result is 500.0", True),
        ("It equals 1,000", False),
        ("five hundred", False),
        ("5000", False),
    ],
)
def test_numeric_expectation(answer, passes):
    case = make_case(expected_answer={"numeric": 500})

    failures = check_agent_case(case, AgentRunOutcome(answer=answer))

    assert (failures == []) is passes


def test_numeric_expectation_handles_thousands_separators():
    case = make_case(expected_answer={"numeric": 1000})

    assert check_agent_case(case, AgentRunOutcome(answer="It is 1,000.")) == []


def test_refusal_cannot_require_number():
    with pytest.raises(ValueError, match="refusal cannot also require"):
        make_case(expected_answer={"refusal": True, "numeric": 1})


@pytest.mark.parametrize(
    "outcome, passes",
    [
        (AgentRunOutcome(answer="It was created by Guido."), False),
        (AgentRunOutcome(answer="I couldn't find that."), True),
        (AgentRunOutcome(answer="It was created by Guido.", contexts=["doc"]), True),
    ],
)
def test_grounded_case_without_context_must_refuse(outcome, passes):
    case = make_case(grounded=True)

    failures = check_agent_case(case, outcome)

    assert (failures == []) is passes
    if not passes:
        assert "possible hallucination" in failures[0]


def test_ungrounded_case_may_answer_without_context():
    case = make_case()

    assert check_agent_case(case, AgentRunOutcome(answer="500")) == []


def test_refusal_expectation():
    case = make_case(expected_answer={"refusal": True})

    assert check_agent_case(case, AgentRunOutcome(answer="Not available.")) == []
    assert check_agent_case(case, AgentRunOutcome(answer="It began in 1981.")) == [
        "answer should say the information is unavailable"
    ]
