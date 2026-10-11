import pytest
from langchain_core.runnables import RunnableLambda

from evals.checks import AgentRunOutcome
from evals.judges import (
    ClaimCheck,
    CorrectnessJudge,
    CorrectnessVerdict,
    FaithfulnessJudge,
    FaithfulnessVerdict,
    JudgeReport,
    Judges,
    RelevanceJudge,
    RelevanceVerdict,
    judge_agent_case,
    summarize,
)
from evals.schema import AgentEvalCase


class FakeJudgeLLM:
    """Returns a fixed verdict and records the prompt it was sent."""

    def __init__(self, verdict):
        self.verdict = verdict
        self.prompts: list[str] = []

    def runnable(self):
        def respond(prompt_value):
            self.prompts.append(prompt_value.to_string())
            return self.verdict

        return RunnableLambda(respond)


def make_case(**overrides) -> AgentEvalCase:
    return AgentEvalCase.model_validate(
        {"id": "case-1", "question": "What is Generative AI?", **overrides}
    )


def correctness(verdict="correct", reason="Matches.") -> FakeJudgeLLM:
    return FakeJudgeLLM(CorrectnessVerdict(verdict=verdict, reason=reason))


def faithfulness(*claims: tuple[str, bool]) -> FakeJudgeLLM:
    return FakeJudgeLLM(make_faithfulness(*claims))


def make_faithfulness(*claims: tuple[str, bool]) -> FaithfulnessVerdict:
    return FaithfulnessVerdict(
        claims=[
            ClaimCheck(claim=claim, supported=supported)
            for claim, supported in claims
        ]
    )


def relevance(verdict="relevant", reason="Answers it.") -> FakeJudgeLLM:
    return FakeJudgeLLM(RelevanceVerdict(verdict=verdict, reason=reason))


async def judge(
    case,
    outcome,
    correctness_llm=None,
    faithfulness_llm=None,
    relevance_llm=None,
) -> JudgeReport:
    judges = Judges(
        correctness=CorrectnessJudge(
            llm=(correctness_llm or correctness()).runnable()
        ),
        faithfulness=FaithfulnessJudge(
            llm=(faithfulness_llm or faithfulness()).runnable()
        ),
        relevance=RelevanceJudge(llm=(relevance_llm or relevance()).runnable()),
    )
    return await judge_agent_case(case, outcome, judges)


@pytest.mark.parametrize(
    "claims, expected",
    [
        ([], None),
        ([("a", True), ("b", True)], 1.0),
        ([("a", True), ("b", False)], 0.5),
        ([("a", False)], 0.0),
    ],
)
def test_faithfulness_score(claims, expected):
    assert make_faithfulness(*claims).score == expected


def test_unsupported_claims_are_listed():
    verdict = make_faithfulness(("supported", True), ("made up", False))

    assert verdict.unsupported_claims == ["made up"]


@pytest.mark.asyncio
async def test_judges_receive_question_reference_evidence_and_answer():
    correctness_llm = correctness()
    faithfulness_llm = faithfulness(("GenAI creates text.", True))
    relevance_llm = relevance()

    case = make_case(reference_answer="It creates new content.")
    outcome = AgentRunOutcome(
        answer="GenAI creates text.",
        contexts=["chunk one"],
        tool_outputs=['{"ok": true, "result": 500}'],
    )

    report = await judge(
        case, outcome, correctness_llm, faithfulness_llm, relevance_llm
    )

    assert report.failures == []

    correctness_prompt = correctness_llm.prompts[0]
    assert "What is Generative AI?" in correctness_prompt
    assert "It creates new content." in correctness_prompt
    assert "GenAI creates text." in correctness_prompt

    faithfulness_prompt = faithfulness_llm.prompts[0]
    assert "[Retrieved document]\nchunk one" in faithfulness_prompt
    assert '[Tool result]\n{"ok": true, "result": 500}' in faithfulness_prompt

    relevance_prompt = relevance_llm.prompts[0]
    assert "What is Generative AI?" in relevance_prompt
    assert "GenAI creates text." in relevance_prompt
    assert "It creates new content." not in relevance_prompt


@pytest.mark.parametrize("verdict", ["partially_correct", "incorrect"])
@pytest.mark.asyncio
async def test_non_correct_verdict_fails(verdict):
    report = await judge(
        make_case(reference_answer="Reference."),
        AgentRunOutcome(answer="Answer."),
        correctness_llm=correctness(verdict, "Misses video."),
    )

    assert report.failures == [f"correctness judge: {verdict} (Misses video.)"]


@pytest.mark.parametrize("verdict", ["partially_relevant", "irrelevant"])
@pytest.mark.asyncio
async def test_non_relevant_verdict_fails(verdict):
    report = await judge(
        make_case(),
        AgentRunOutcome(answer="Foundation models exist."),
        relevance_llm=relevance(verdict, "Off topic."),
    )

    assert report.failures == [f"relevance judge: {verdict} (Off topic.)"]


@pytest.mark.asyncio
async def test_unfaithful_answer_is_flagged_as_hallucination():
    report = await judge(
        make_case(),
        AgentRunOutcome(answer="x", contexts=["context"]),
        faithfulness_llm=faithfulness(("in context", True), ("invented", False)),
    )

    assert report.hallucinated is True
    assert report.failures == [
        "faithfulness 0.50 < 0.9; unsupported claims: ['invented']"
    ]


@pytest.mark.asyncio
async def test_tool_output_alone_is_enough_evidence_for_faithfulness():
    faithfulness_llm = faithfulness(("125 * 4 is 500", True))

    report = await judge(
        make_case(question="What is 125 * 4?"),
        AgentRunOutcome(
            answer="125 * 4 is 500.",
            tool_outputs=['{"ok": true, "result": 500}'],
        ),
        faithfulness_llm=faithfulness_llm,
    )

    assert faithfulness_llm.prompts
    assert report.hallucinated is False


@pytest.mark.asyncio
async def test_judges_are_skipped_when_not_applicable():
    correctness_llm = correctness()
    faithfulness_llm = faithfulness()
    relevance_llm = relevance()

    # No reference, no evidence, refusal expected: no judge calls at all.
    report = await judge(
        make_case(expected_answer={"refusal": True}),
        AgentRunOutcome(answer="I couldn't find that."),
        correctness_llm,
        faithfulness_llm,
        relevance_llm,
    )

    assert report == JudgeReport(case_id="case-1")
    assert correctness_llm.prompts == []
    assert faithfulness_llm.prompts == []
    assert relevance_llm.prompts == []


@pytest.mark.asyncio
async def test_answer_without_claims_is_not_scored():
    report = await judge(
        make_case(),
        AgentRunOutcome(answer="I couldn't find that.", contexts=["unrelated"]),
    )

    assert report.hallucinated is None
    assert report.failures == []


def test_summarize_rates_only_count_cases_each_judge_applied_to():
    reports = [
        JudgeReport(
            case_id="good",
            correctness=CorrectnessVerdict(verdict="correct", reason=""),
            faithfulness=make_faithfulness(("a", True)),
            relevance=RelevanceVerdict(verdict="relevant", reason=""),
        ),
        JudgeReport(
            case_id="hallucinated",
            correctness=CorrectnessVerdict(verdict="incorrect", reason=""),
            faithfulness=make_faithfulness(("a", True), ("b", False)),
            relevance=RelevanceVerdict(verdict="irrelevant", reason=""),
        ),
        JudgeReport(
            case_id="calculator",
            faithfulness=make_faithfulness(("500", True)),
            relevance=RelevanceVerdict(verdict="relevant", reason=""),
        ),
        JudgeReport(case_id="refusal"),
    ]

    summary = summarize(reports)

    assert summary.cases == 4
    assert summary.correctness_accuracy == 0.5
    assert summary.mean_faithfulness == pytest.approx((1.0 + 0.5 + 1.0) / 3)
    assert summary.hallucination_rate == pytest.approx(1 / 3)
    assert summary.relevance_rate == pytest.approx(2 / 3)
    assert summary.hallucinated_case_ids == ["hallucinated"]


def test_summarize_with_no_applicable_judges():
    summary = summarize([JudgeReport(case_id="refusal")])

    assert summary.correctness_accuracy is None
    assert summary.mean_faithfulness is None
    assert summary.hallucination_rate is None
    assert summary.relevance_rate is None
