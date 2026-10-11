import pytest

from evals.agent_runner import run_agent
from evals.checks import check_agent_case
from evals.judges import Judges, judge_agent_case, summarize
from evals.schema import load_agent_cases

pytestmark = pytest.mark.live

AGENT_EVALUATION_DATASET = load_agent_cases()


@pytest.fixture(scope="module")
def judge_reports():
    reports = []

    yield reports

    if reports:
        summary = summarize(reports)
        print("\n--- Agent Evaluation Report ---")
        print(f"Cases judged: {summary.cases}")
        print(f"Correctness accuracy: {summary.correctness_accuracy}")
        print(f"Mean faithfulness: {summary.mean_faithfulness}")
        print(f"Hallucination rate: {summary.hallucination_rate}")
        print(f"Relevance rate: {summary.relevance_rate}")
        print(f"Hallucinated cases: {summary.hallucinated_case_ids}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    AGENT_EVALUATION_DATASET,
    ids=[case.id for case in AGENT_EVALUATION_DATASET],
)
async def test_agent_evaluation_case(case, judge_reports):
    outcome = await run_agent(case.question)

    failures = check_agent_case(case, outcome)

    # Judges cost an extra LLM call each, so skip them once a cheap rule fails.
    if not failures:
        report = await judge_agent_case(case, outcome, Judges.default())
        judge_reports.append(report)
        failures = report.failures

    assert not failures, (
        f"{case.id}: {'; '.join(failures)}\nAnswer: {outcome.answer}"
    )
