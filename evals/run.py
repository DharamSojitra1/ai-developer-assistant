"""Run the evaluation datasets and produce a summary report.

    python -m evals.run                        # agent + RAG suites, with judges
    python -m evals.run --suite rag            # retrieval only
    python -m evals.run --ids calc-multiply,rag-genai-outputs
    python -m evals.run --tags negative --no-judges

Every case calls paid APIs (Groq, Gemini); use --ids, --tags, or --suite to
limit cost. The report is printed and written as JSON to evals/reports/.
Exit code: 0 if every case passed, 1 if any failed, 2 for bad arguments.
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import GROQ_MODEL_NAME, RAG_FINAL_TOP_K
from evals.checks import AgentRunOutcome, check_agent_case, is_ungrounded
from evals.judges import JudgeReport, Judges, judge_agent_case
from evals.metrics import (
    calculate_false_positive_rate,
    calculate_hit_rate,
    calculate_mrr_at_k,
    latency_stats,
)
from evals.pricing import unpriced_models
from evals.schema import (
    AgentEvalCase,
    RagEvalCase,
    load_agent_cases,
    load_rag_cases,
)
from evals.usage import RunUsage, measure_usage

REPORTS_DIR = Path(__file__).parent / "reports"

AgentRunner = Callable[[str], Awaitable[AgentRunOutcome]]
Retriever = Callable[[str], Awaitable[list[dict]]]


# ---------------------------------------------------------------- agent suite


@dataclass
class AgentCaseResult:
    case: AgentEvalCase
    outcome: AgentRunOutcome | None = None
    failures: list[str] = field(default_factory=list)
    judge_report: JudgeReport | None = None
    judge_usage: RunUsage = field(default_factory=RunUsage)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and not self.failures

    @property
    def tools_correct(self) -> bool | None:
        if not self.case.expected_tools or self.outcome is None:
            return None

        return all(
            tool in self.outcome.tools_called
            for tool in self.case.expected_tools
        )

    @property
    def hallucinated(self) -> bool | None:
        """True/False when it could be determined, None otherwise.

        Combines the free grounding rule (answered with nothing retrieved)
        with the faithfulness judge (claims missing from the evidence).
        """
        if self.outcome is None:
            return None

        if is_ungrounded(self.case, self.outcome):
            return True

        if self.judge_report and self.judge_report.hallucinated is not None:
            return self.judge_report.hallucinated

        if self.case.grounded and not self.outcome.contexts:
            # Nothing retrieved and the agent correctly refused.
            return False

        return None

    def to_dict(self) -> dict:
        report = self.judge_report
        outcome = self.outcome

        return {
            "id": self.case.id,
            "question": self.case.question,
            "tags": self.case.tags,
            "passed": self.passed,
            "error": self.error,
            "failures": self.failures,
            "answer": outcome.answer if outcome else None,
            "tools_called": outcome.tools_called if outcome else [],
            "source_ids": outcome.source_ids if outcome else [],
            "hallucinated": self.hallucinated,
            "usage": outcome.usage.to_dict() if outcome else None,
            "judge_usage": self.judge_usage.to_dict(),
            "judges": {
                "correctness": (
                    report.correctness.model_dump()
                    if report and report.correctness
                    else None
                ),
                "faithfulness_score": (
                    report.faithfulness.score
                    if report and report.faithfulness
                    else None
                ),
                "unsupported_claims": (
                    report.faithfulness.unsupported_claims
                    if report and report.faithfulness
                    else []
                ),
                "relevance": (
                    report.relevance.model_dump()
                    if report and report.relevance
                    else None
                ),
            },
        }


async def evaluate_agent_case(
    case: AgentEvalCase,
    run_agent: AgentRunner,
    judges: Judges | None,
) -> AgentCaseResult:
    result = AgentCaseResult(case=case)

    try:
        result.outcome = await run_agent(case.question)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    result.failures = check_agent_case(case, result.outcome)

    # Unlike the pytest suite, judges run even when a rule failed, so the
    # judge metrics cover every case they apply to.
    if judges is not None:
        try:
            with measure_usage() as measurement:
                result.judge_report = await judge_agent_case(
                    case,
                    result.outcome,
                    judges,
                )
            result.failures.extend(result.judge_report.failures)
        except Exception as exc:
            result.error = f"judge failed: {type(exc).__name__}: {exc}"
        finally:
            result.judge_usage = measurement.usage

    return result


def _rate(values: list[bool]) -> dict | None:
    if not values:
        return None

    return {"rate": sum(values) / len(values), "count": len(values)}


def _usage_summary(usages: list[RunUsage]) -> dict:
    total = sum(usages, RunUsage())
    runs = len(usages)

    return {
        "runs": runs,
        "total_input_tokens": total.input_tokens,
        "total_output_tokens": total.output_tokens,
        "total_tokens": total.total_tokens,
        "mean_tokens_per_run": total.total_tokens / runs if runs else None,
        "total_cost_usd": total.cost_usd,
        "mean_cost_usd_per_run": (
            total.cost_usd / runs
            if runs and total.cost_usd is not None
            else None
        ),
        "unpriced_models": unpriced_models(total.models),
        "latency_seconds": latency_stats(
            [usage.latency_seconds for usage in usages]
        ),
    }


def summarize_agent(results: list[AgentCaseResult]) -> dict:
    reports = [result.judge_report for result in results if result.judge_report]
    faithfulness_scores = [
        report.faithfulness.score
        for report in reports
        if report.faithfulness and report.faithfulness.score is not None
    ]

    return {
        "cases": len(results),
        "passed": sum(result.passed for result in results),
        "errors": sum(result.error is not None for result in results),
        "pass_rate": _rate([result.passed for result in results]),
        "tool_selection_accuracy": _rate(
            [
                result.tools_correct
                for result in results
                if result.tools_correct is not None
            ]
        ),
        "correctness_accuracy": _rate(
            [
                report.correctness.verdict == "correct"
                for report in reports
                if report.correctness
            ]
        ),
        "mean_faithfulness": (
            sum(faithfulness_scores) / len(faithfulness_scores)
            if faithfulness_scores
            else None
        ),
        "hallucination_rate": _rate(
            [
                result.hallucinated
                for result in results
                if result.hallucinated is not None
            ]
        ),
        "relevance_rate": _rate(
            [
                report.relevance.verdict == "relevant"
                for report in reports
                if report.relevance
            ]
        ),
        "agent_usage": _usage_summary(
            [result.outcome.usage for result in results if result.outcome]
        ),
        "judge_usage": _usage_summary(
            [result.judge_usage for result in results if result.judge_report]
        ),
    }


async def run_agent_suite(
    cases: Sequence[AgentEvalCase],
    run_agent: AgentRunner,
    judges: Judges | None,
) -> dict:
    # Sequential on purpose: keeps latency numbers honest and avoids rate limits.
    results = [
        await evaluate_agent_case(case, run_agent, judges)
        for case in cases
    ]

    return {
        "summary": summarize_agent(results),
        "cases": [result.to_dict() for result in results],
    }


# ------------------------------------------------------------------ RAG suite


@dataclass
class RagCaseResult:
    case: RagEvalCase
    documents: list[dict] = field(default_factory=list)
    usage: RunUsage = field(default_factory=RunUsage)
    error: str | None = None

    @property
    def document_ids(self) -> list[str]:
        return [
            document["metadata"]["document_id"]
            for document in self.documents
        ]

    @property
    def passed(self) -> bool:
        if self.error is not None:
            return False

        if self.case.expected_document_id is None:
            return not self.documents

        return self.case.expected_document_id in self.document_ids

    def to_dict(self) -> dict:
        return {
            "id": self.case.id,
            "query": self.case.query,
            "tags": self.case.tags,
            "expected_document_id": self.case.expected_document_id,
            "retrieved_document_ids": self.document_ids,
            "passed": self.passed,
            "error": self.error,
            "usage": self.usage.to_dict(),
        }


async def evaluate_rag_case(
    case: RagEvalCase,
    retrieve: Retriever,
) -> RagCaseResult:
    result = RagCaseResult(case=case)

    try:
        with measure_usage() as measurement:
            result.documents = await retrieve(case.query)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        result.usage = measurement.usage

    return result


def summarize_rag(results: list[RagCaseResult], k: int) -> dict:
    retrieved = [result.documents for result in results]
    cases = [
        {"expected_document_id": result.case.expected_document_id}
        for result in results
    ]
    # Hit rate and MRR are undefined without positive queries; report None
    # rather than a misleading 0.0.
    has_positive = any(case["expected_document_id"] for case in cases)

    return {
        "cases": len(results),
        "passed": sum(result.passed for result in results),
        "errors": sum(result.error is not None for result in results),
        "pass_rate": _rate([result.passed for result in results]),
        f"hit_rate_at_{k}": (
            calculate_hit_rate(retrieved, cases) if has_positive else None
        ),
        f"mrr_at_{k}": (
            calculate_mrr_at_k(retrieved, cases, k=k) if has_positive else None
        ),
        "false_positive_rate": calculate_false_positive_rate(retrieved, cases),
        "usage": _usage_summary([result.usage for result in results]),
    }


async def run_rag_suite(
    cases: Sequence[RagEvalCase],
    retrieve: Retriever,
    k: int = RAG_FINAL_TOP_K,
) -> dict:
    results = [await evaluate_rag_case(case, retrieve) for case in cases]

    return {
        "summary": summarize_rag(results, k=k),
        "cases": [result.to_dict() for result in results],
    }


# -------------------------------------------------------------------- report


def _pct(metric: dict | None) -> str:
    if metric is None:
        return "n/a"

    count = metric["count"]
    return f"{metric['rate']:.1%} ({count} case{'' if count == 1 else 's'})"


def _num(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _usage_lines(label: str, usage: dict) -> list[str]:
    latency = usage["latency_seconds"]
    cost = usage["total_cost_usd"]
    lines = []

    if latency:
        lines.append(
            f"{label} latency (s): mean {latency['mean']:.2f}, "
            f"p50 {latency['p50']:.2f}, p95 {latency['p95']:.2f}, "
            f"max {latency['max']:.2f}"
        )

    lines.append(
        f"{label} tokens: {usage['total_tokens']} total "
        f"(in {usage['total_input_tokens']} / out {usage['total_output_tokens']}), "
        f"mean {_num(usage['mean_tokens_per_run'], 0)} per run"
    )
    lines.append(
        f"{label} cost: "
        + (
            f"${cost:.4f} total, ${usage['mean_cost_usd_per_run']:.5f} per run"
            if cost is not None
            else f"unknown (no price for {usage['unpriced_models']})"
        )
    )

    return lines


def format_report(report: dict) -> str:
    lines = [
        f"Evaluation report ({report['generated_at']}, model {report['model']})",
    ]

    agent = report["suites"].get("agent")
    if agent:
        summary = agent["summary"]
        lines += [
            "",
            f"=== Agent ({summary['cases']} cases) ===",
            f"Passed: {summary['passed']}/{summary['cases']}"
            + (f" ({summary['errors']} errors)" if summary["errors"] else ""),
            f"Tool selection accuracy: {_pct(summary['tool_selection_accuracy'])}",
            f"Correctness accuracy: {_pct(summary['correctness_accuracy'])}",
            f"Mean faithfulness: {_num(summary['mean_faithfulness'])}",
            f"Hallucination rate: {_pct(summary['hallucination_rate'])}",
            f"Relevance rate: {_pct(summary['relevance_rate'])}",
            *_usage_lines("Agent", summary["agent_usage"]),
        ]

        if summary["judge_usage"]["runs"]:
            lines += _usage_lines("Judge", summary["judge_usage"])

        lines += _failure_lines(agent["cases"])

    rag = report["suites"].get("rag")
    if rag:
        summary = rag["summary"]
        k = report["rag_top_k"]
        lines += [
            "",
            f"=== RAG retrieval ({summary['cases']} cases) ===",
            f"Passed: {summary['passed']}/{summary['cases']}"
            + (f" ({summary['errors']} errors)" if summary["errors"] else ""),
            f"Hit Rate@{k}: {_num(summary[f'hit_rate_at_{k}'], 3)}",
            f"MRR@{k}: {_num(summary[f'mrr_at_{k}'], 3)}",
            f"False-positive rate: {_num(summary['false_positive_rate'], 3)}",
            *_usage_lines("Retrieval", summary["usage"]),
        ]
        lines += _failure_lines(rag["cases"])

    return "\n".join(lines)


def _failure_lines(cases: list[dict]) -> list[str]:
    failed = [case for case in cases if not case["passed"]]

    if not failed:
        return []

    lines = ["Failed cases:"]
    for case in failed:
        reasons = case.get("failures") or []
        if case["error"]:
            reasons = [case["error"], *reasons]
        if not reasons and "retrieved_document_ids" in case:
            reasons = [
                f"expected {case['expected_document_id']}, "
                f"retrieved {case['retrieved_document_ids']}"
            ]
        lines.append(f"  - {case['id']}: {'; '.join(reasons)}")

    return lines


def all_passed(report: dict) -> bool:
    return all(
        case["passed"]
        for suite in report["suites"].values()
        for case in suite["cases"]
    )


def write_report(report: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"eval-{timestamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


# ----------------------------------------------------------------------- CLI


def select_cases(cases, ids: set[str] | None, tags: set[str] | None):
    return [
        case
        for case in cases
        if (ids is None or case.id in ids)
        and (tags is None or tags.intersection(case.tags))
    ]


def _csv(value: str | None) -> set[str] | None:
    if value is None:
        return None

    return {item.strip() for item in value.split(",") if item.strip()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals.run",
        description="Run the evaluation datasets (paid API calls).",
    )
    parser.add_argument("--suite", choices=["agent", "rag", "all"], default="all")
    parser.add_argument("--ids", help="Comma-separated case IDs to run.")
    parser.add_argument("--tags", help="Run cases that have any of these tags.")
    parser.add_argument(
        "--no-judges",
        action="store_true",
        help="Skip the LLM judges (cheaper; no correctness/faithfulness/relevance).",
    )
    parser.add_argument("--output-dir", type=Path, default=REPORTS_DIR)
    return parser


async def run(
    suite: str,
    agent_cases: Sequence[AgentEvalCase],
    rag_cases: Sequence[RagEvalCase],
    run_agent: AgentRunner,
    retrieve: Retriever,
    judges: Judges | None,
) -> dict:
    suites = {}

    if suite in ("agent", "all") and agent_cases:
        suites["agent"] = await run_agent_suite(agent_cases, run_agent, judges)

    if suite in ("rag", "all") and rag_cases:
        suites["rag"] = await run_rag_suite(rag_cases, retrieve)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": GROQ_MODEL_NAME,
        "rag_top_k": RAG_FINAL_TOP_K,
        "judges": judges is not None,
        "suites": suites,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ids, tags = _csv(args.ids), _csv(args.tags)

    agent_cases = select_cases(load_agent_cases(), ids, tags)
    rag_cases = select_cases(load_rag_cases(), ids, tags)

    if args.suite == "agent":
        rag_cases = []
    elif args.suite == "rag":
        agent_cases = []

    if ids:
        unknown = ids - {case.id for case in [*agent_cases, *rag_cases]}
        if unknown:
            print(f"Unknown case IDs for this suite: {sorted(unknown)}", file=sys.stderr)
            return 2

    if not agent_cases and not rag_cases:
        print("No cases match the given filters.", file=sys.stderr)
        return 2

    # Imported lazily: these load models and API clients.
    from app.services.rag_service import RAGService
    from evals.agent_runner import run_agent

    async def retrieve(query: str) -> list[dict]:
        return await rag_service.retrieve(query=query, top_k=RAG_FINAL_TOP_K)

    rag_service = RAGService() if rag_cases else None
    judges = None if args.no_judges else Judges.default()

    report = asyncio.run(
        run(args.suite, agent_cases, rag_cases, run_agent, retrieve, judges)
    )

    path = write_report(report, args.output_dir)
    print(format_report(report))
    print(f"\nFull report: {path}")

    return 0 if all_passed(report) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    sys.exit(main())
