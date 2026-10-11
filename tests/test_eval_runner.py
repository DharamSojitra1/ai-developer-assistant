import json

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from evals import run as runner
from evals.checks import AgentRunOutcome
from evals.judges import (
    ClaimCheck,
    CorrectnessJudge,
    CorrectnessVerdict,
    FaithfulnessJudge,
    FaithfulnessVerdict,
    Judges,
    RelevanceJudge,
    RelevanceVerdict,
)
from evals.metrics import (
    calculate_false_positive_rate,
    latency_stats,
    percentile,
)
from evals.pricing import estimate_cost, unpriced_models
from evals.schema import AgentEvalCase, RagEvalCase
from evals.usage import ModelUsage, RunUsage, measure_usage


def fake_model(model_name: str, input_tokens: int, output_tokens: int):
    return FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="ok",
                usage_metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                response_metadata={"model_name": model_name},
            )
        ]
        * 5
    )


def agent_case(**overrides) -> AgentEvalCase:
    return AgentEvalCase.model_validate({"question": "Q?", **overrides})


def rag_case(case_id: str, expected: str | None) -> RagEvalCase:
    return RagEvalCase(id=case_id, query=f"{case_id}?", expected_document_id=expected)


def fixed_judges(
    correctness="correct",
    claims=(("claim", True),),
    relevance="relevant",
) -> Judges:
    def returning(verdict):
        return RunnableLambda(lambda _prompt: verdict)

    return Judges(
        correctness=CorrectnessJudge(
            llm=returning(CorrectnessVerdict(verdict=correctness, reason="r"))
        ),
        faithfulness=FaithfulnessJudge(
            llm=returning(
                FaithfulnessVerdict(
                    claims=[
                        ClaimCheck(claim=claim, supported=supported)
                        for claim, supported in claims
                    ]
                )
            )
        ),
        relevance=RelevanceJudge(
            llm=returning(RelevanceVerdict(verdict=relevance, reason="r"))
        ),
    )


# ------------------------------------------------------------- usage + cost


@pytest.mark.asyncio
async def test_measure_usage_captures_nested_calls_per_model():
    agent_llm = fake_model("openai/gpt-oss-120b", 100, 20)
    other_llm = fake_model("other-model", 7, 3)

    async def nested_tool():
        # Not passed any callbacks: captured through the context variable.
        await other_llm.ainvoke("inner")

    with measure_usage() as measurement:
        await agent_llm.ainvoke("first")
        await nested_tool()
        await agent_llm.ainvoke("second")

    usage = measurement.usage

    assert usage.models == {
        "openai/gpt-oss-120b": ModelUsage(input_tokens=200, output_tokens=40),
        "other-model": ModelUsage(input_tokens=7, output_tokens=3),
    }
    assert usage.total_tokens == 250
    assert usage.latency_seconds > 0


@pytest.mark.asyncio
async def test_measure_usage_records_usage_even_when_block_raises():
    llm = fake_model("openai/gpt-oss-120b", 10, 5)

    with pytest.raises(RuntimeError):
        with measure_usage() as measurement:
            await llm.ainvoke("hi")
            raise RuntimeError("boom")

    assert measurement.usage.total_tokens == 15


@pytest.mark.asyncio
async def test_usage_outside_block_is_not_counted():
    llm = fake_model("openai/gpt-oss-120b", 10, 5)

    with measure_usage() as measurement:
        pass

    await llm.ainvoke("after")

    assert measurement.usage.total_tokens == 0


def test_estimate_cost_uses_per_million_prices():
    usage = {"m": ModelUsage(input_tokens=2_000_000, output_tokens=1_000_000)}

    assert estimate_cost(usage, prices={"m": (0.5, 2.0)}) == pytest.approx(3.0)


def test_unknown_model_price_gives_no_cost_instead_of_zero():
    usage = {"known": ModelUsage(1, 1), "mystery": ModelUsage(1, 1)}
    prices = {"known": (1.0, 1.0)}

    assert estimate_cost(usage, prices=prices) is None
    assert unpriced_models(usage, prices=prices) == ["mystery"]


def test_run_usage_addition_merges_models_and_latency():
    total = RunUsage(1.0, {"a": ModelUsage(1, 2)}) + RunUsage(
        0.5, {"a": ModelUsage(3, 4), "b": ModelUsage(5, 6)}
    )

    assert total.latency_seconds == 1.5
    assert total.models == {"a": ModelUsage(4, 6), "b": ModelUsage(5, 6)}


# ------------------------------------------------------------------ metrics


def test_percentile_interpolates():
    values = [1.0, 2.0, 3.0, 4.0]

    assert percentile(values, 0.5) == 2.5
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 1.0) == 4.0
    assert percentile([7.0], 0.95) == 7.0


@pytest.mark.parametrize("values, fraction", [([], 0.5), ([1.0], 1.5)])
def test_percentile_rejects_bad_input(values, fraction):
    with pytest.raises(ValueError):
        percentile(values, fraction)


def test_latency_stats():
    assert latency_stats([]) is None
    assert latency_stats([1.0, 3.0]) == {
        "mean": 2.0,
        "p50": 2.0,
        "p95": pytest.approx(2.9),
        "max": 3.0,
    }


def test_false_positive_rate_counts_only_negative_queries():
    cases = [
        {"expected_document_id": None},
        {"expected_document_id": None},
        {"expected_document_id": "doc"},
    ]
    results = [[{"metadata": {"document_id": "x"}}], [], []]

    assert calculate_false_positive_rate(results, cases) == 0.5
    assert calculate_false_positive_rate([[]], [{"expected_document_id": "d"}]) is None


# ------------------------------------------------------------------- runner


def outcome(answer, **kwargs) -> AgentRunOutcome:
    return AgentRunOutcome(
        answer=answer,
        usage=RunUsage(
            latency_seconds=kwargs.pop("latency", 1.0),
            models={"openai/gpt-oss-120b": ModelUsage(1000, 100)},
        ),
        **kwargs,
    )


AGENT_CASES = [
    agent_case(
        id="calc",
        question="What is 2 + 2?",
        expected_tools=["calculator"],
        expected_answer={"numeric": 4},
    ),
    agent_case(
        id="kb",
        question="KB question?",
        expected_tools=["search_knowledge_base"],
        reference_answer="Reference.",
        grounded=True,
    ),
    agent_case(
        id="made-up",
        question="Who created Python?",
        expected_answer={"refusal": True},
        grounded=True,
    ),
]

OUTCOMES = {
    "What is 2 + 2?": outcome(
        "It is 4.",
        tools_called=["calculator"],
        tool_outputs=['{"ok": true, "result": 4}'],
        latency=1.0,
    ),
    "KB question?": outcome(
        "Answer from docs.",
        tools_called=["search_knowledge_base"],
        contexts=["doc text"],
        latency=2.0,
    ),
    # Answers from training data with nothing retrieved: a hallucination.
    "Who created Python?": outcome("Guido van Rossum.", latency=3.0),
}


async def fake_run_agent(question: str) -> AgentRunOutcome:
    return OUTCOMES[question]


async def fake_retrieve(query: str) -> list[dict]:
    documents = {
        "hit?": ["doc-a"],
        "second?": ["doc-x", "doc-b"],
        "miss?": ["doc-x"],
        "negative-ok?": [],
        "negative-bad?": ["doc-a"],
    }[query]
    return [{"metadata": {"document_id": doc}} for doc in documents]


RAG_CASES = [
    rag_case("hit", "doc-a"),
    rag_case("second", "doc-b"),
    rag_case("miss", "doc-c"),
    rag_case("negative-ok", None),
    rag_case("negative-bad", None),
]


async def run_all(judges=None, run_agent=fake_run_agent):
    return await runner.run(
        "all",
        AGENT_CASES,
        RAG_CASES,
        run_agent,
        fake_retrieve,
        judges if judges is not None else fixed_judges(),
    )


@pytest.mark.asyncio
async def test_agent_summary_metrics():
    report = await run_all()
    summary = report["suites"]["agent"]["summary"]

    assert summary["cases"] == 3
    assert summary["passed"] == 2
    assert summary["tool_selection_accuracy"] == {"rate": 1.0, "count": 2}
    assert summary["correctness_accuracy"] == {"rate": 1.0, "count": 1}
    assert summary["mean_faithfulness"] == 1.0
    # calc and kb were judged faithful; made-up broke the grounding rule.
    assert summary["hallucination_rate"]["count"] == 3
    assert summary["hallucination_rate"]["rate"] == pytest.approx(1 / 3)
    assert summary["relevance_rate"] == {"rate": 1.0, "count": 2}

    usage = summary["agent_usage"]
    assert usage["total_input_tokens"] == 3000
    assert usage["total_output_tokens"] == 300
    assert usage["mean_tokens_per_run"] == 1100
    assert usage["latency_seconds"]["mean"] == 2.0
    assert usage["latency_seconds"]["max"] == 3.0
    assert usage["total_cost_usd"] == pytest.approx(
        3 * (1000 * 0.15 + 100 * 0.75) / 1_000_000
    )


@pytest.mark.asyncio
async def test_agent_case_records_failures_and_judge_verdicts():
    report = await run_all(judges=fixed_judges(claims=(("x", False),)))
    cases = {case["id"]: case for case in report["suites"]["agent"]["cases"]}

    assert cases["kb"]["passed"] is False
    assert cases["kb"]["hallucinated"] is True
    assert cases["kb"]["judges"]["unsupported_claims"] == ["x"]
    assert any("possible hallucination" in f for f in cases["made-up"]["failures"])
    assert cases["calc"]["usage"]["total_tokens"] == 1100


@pytest.mark.asyncio
async def test_agent_errors_are_reported_not_raised():
    async def broken_agent(question):
        raise TimeoutError("Groq timed out")

    report = await run_all(run_agent=broken_agent)
    summary = report["suites"]["agent"]["summary"]

    assert summary["errors"] == 3
    assert summary["passed"] == 0
    assert report["suites"]["agent"]["cases"][0]["error"] == (
        "TimeoutError: Groq timed out"
    )
    assert summary["agent_usage"]["latency_seconds"] is None


@pytest.mark.asyncio
async def test_no_judges_mode_skips_judge_metrics():
    report = await runner.run(
        "agent", AGENT_CASES, [], fake_run_agent, fake_retrieve, None
    )
    summary = report["suites"]["agent"]["summary"]

    assert summary["correctness_accuracy"] is None
    assert summary["relevance_rate"] is None
    assert summary["judge_usage"]["runs"] == 0
    assert "rag" not in report["suites"]


@pytest.mark.asyncio
async def test_rag_summary_metrics():
    report = await run_all()
    summary = report["suites"]["rag"]["summary"]
    k = report["rag_top_k"]

    assert summary["passed"] == 3
    assert summary[f"hit_rate_at_{k}"] == pytest.approx(2 / 3)
    assert summary[f"mrr_at_{k}"] == pytest.approx((1 + 0.5 + 0) / 3)
    assert summary["false_positive_rate"] == 0.5


@pytest.mark.asyncio
async def test_rag_ranking_metrics_are_none_without_positive_queries():
    report = await runner.run(
        "rag",
        [],
        [rag_case("negative-ok", None)],
        fake_run_agent,
        fake_retrieve,
        None,
    )
    summary = report["suites"]["rag"]["summary"]
    k = report["rag_top_k"]

    assert summary[f"hit_rate_at_{k}"] is None
    assert summary[f"mrr_at_{k}"] is None
    assert f"Hit Rate@{k}: n/a" in runner.format_report(report)


@pytest.mark.asyncio
async def test_report_is_formatted_and_written(tmp_path):
    report = await run_all()

    text = runner.format_report(report)

    assert "=== Agent (3 cases) ===" in text
    assert "Hallucination rate: 33.3% (3 cases)" in text
    assert "Agent latency (s): mean 2.00" in text
    assert "Agent cost: $" in text
    assert "made-up: " in text
    assert "=== RAG retrieval (5 cases) ===" in text
    assert "miss: expected doc-c, retrieved ['doc-x']" in text
    assert runner.all_passed(report) is False

    path = runner.write_report(report, tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["suites"]["agent"]["summary"]["cases"] == 3
    assert saved["model"]


def test_select_cases_by_ids_and_tags():
    cases = [
        agent_case(id="a", tags=["rag"]),
        agent_case(id="b", tags=["calculator"]),
        agent_case(id="c", tags=["rag", "negative"]),
    ]

    assert [c.id for c in runner.select_cases(cases, {"a", "b"}, None)] == ["a", "b"]
    assert [c.id for c in runner.select_cases(cases, None, {"negative"})] == ["c"]
    assert [c.id for c in runner.select_cases(cases, {"a"}, {"negative"})] == []


@pytest.mark.parametrize(
    "argv",
    [
        ["--ids", "does-not-exist"],
        # calc-multiply is an agent case, so it is unknown to the RAG suite.
        ["--suite", "rag", "--ids", "calc-multiply"],
        ["--tags", "no-such-tag"],
    ],
)
def test_main_rejects_filters_that_match_nothing(argv, capsys):
    assert runner.main(argv) == 2
    assert capsys.readouterr().err
