"""Compare an agent run against the expectations of an evaluation case."""

import math
import re
from dataclasses import dataclass, field

from evals.schema import AgentEvalCase
from evals.usage import RunUsage

# LLMs phrase refusals many ways; typographic apostrophes are normalised
# before matching.
REFUSAL_PHRASES = (
    "don't have enough information",
    "doesn't have enough information",
    "not have enough information",
    "not enough information",
    "not available",
    "cannot find",
    "can't find",
    "couldn't find",
    "could not find",
    "unable to find",
    "unable to locate",
    "wasn't able to",
    "was not able to",
    "no information",
    "not provided",
    "no reference",
    "i'm sorry",
    "cannot answer",
)


NUMBER_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class AgentRunOutcome:
    answer: str
    tools_called: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    # Retrieved chunk texts and raw tool results, used by the faithfulness
    # judge as the evidence the answer may rely on.
    contexts: list[str] = field(default_factory=list)
    tool_outputs: list[str] = field(default_factory=list)
    usage: RunUsage = field(default_factory=RunUsage)


def normalize(text: str) -> str:
    return text.lower().replace("\u2019", "'")


def numbers_in(text: str) -> list[float]:
    numbers = []

    for match in NUMBER_PATTERN.findall(text):
        try:
            numbers.append(float(match.replace(",", "")))
        except ValueError:
            continue

    return numbers


def contains_number(text: str, expected: float) -> bool:
    return any(
        math.isclose(number, expected, rel_tol=1e-9, abs_tol=1e-9)
        for number in numbers_in(text)
    )


def is_refusal(answer: str) -> bool:
    answer = normalize(answer)
    return any(phrase in answer for phrase in REFUSAL_PHRASES)


def is_ungrounded(case: AgentEvalCase, outcome: AgentRunOutcome) -> bool:
    """A grounded case answered without retrieved context and without refusing."""
    return (
        case.grounded
        and not outcome.contexts
        and not is_refusal(outcome.answer)
    )


def check_agent_case(
    case: AgentEvalCase,
    outcome: AgentRunOutcome,
) -> list[str]:
    """Return a human-readable failure per unmet expectation (empty = pass)."""
    failures = []

    missing_tools = [
        tool
        for tool in case.expected_tools
        if tool not in outcome.tools_called
    ]
    if missing_tools:
        failures.append(
            f"expected tools {missing_tools} were not called "
            f"(called: {outcome.tools_called})"
        )

    answer = normalize(outcome.answer)
    expected = case.expected_answer

    missing_phrases = [
        phrase
        for phrase in expected.contains
        if normalize(phrase) not in answer
    ]
    if missing_phrases:
        failures.append(f"answer is missing {missing_phrases}")

    if expected.contains_any and not any(
        normalize(phrase) in answer
        for phrase in expected.contains_any
    ):
        failures.append(
            f"answer contains none of {expected.contains_any}"
        )

    if expected.numeric is not None and not contains_number(
        outcome.answer,
        expected.numeric,
    ):
        failures.append(
            f"answer does not contain the number {expected.numeric:g}"
        )

    if expected.refusal and not is_refusal(outcome.answer):
        failures.append("answer should say the information is unavailable")

    if is_ungrounded(case, outcome):
        failures.append(
            "possible hallucination: nothing was retrieved but the answer "
            "is not a refusal"
        )

    if case.expected_sources is not None:
        if not case.expected_sources and outcome.source_ids:
            failures.append(
                f"expected no sources, got {outcome.source_ids}"
            )

        missing_sources = [
            source
            for source in case.expected_sources
            if source not in outcome.source_ids
        ]
        if missing_sources:
            failures.append(
                f"expected sources {missing_sources} are missing "
                f"(got: {outcome.source_ids})"
            )

    return failures
