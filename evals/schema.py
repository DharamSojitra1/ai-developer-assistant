"""Evaluation dataset schema and loaders.

Datasets live in ``evals/datasets/*.jsonl``: one JSON object per line, so
cases diff cleanly and can be added without touching Python. Blank lines and
lines starting with ``#`` are ignored. Every line is validated, and any
error is reported with its file and line number.
"""

import json
from pathlib import Path
from typing import Annotated, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from app.tools.registry import TOOL_REGISTRY

DATASETS_DIR = Path(__file__).parent / "datasets"
AGENT_DATASET = DATASETS_DIR / "agent.jsonl"
RAG_DATASET = DATASETS_DIR / "rag.jsonl"

KNOWN_TOOLS = frozenset(spec.name for spec in TOOL_REGISTRY)


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")

    return value


def _known_tool(value: str) -> str:
    if value not in KNOWN_TOOLS:
        raise ValueError(
            f"unknown tool {value!r}; expected one of {sorted(KNOWN_TOOLS)}"
        )

    return value


NonBlankStr = Annotated[str, AfterValidator(_reject_blank)]
ToolName = Annotated[str, AfterValidator(_known_tool)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnswerExpectation(StrictModel):
    """Rules the final answer must satisfy (matched case-insensitively).

    LLM wording varies between runs, so answers are checked against rules
    rather than an exact reference string.
    """

    contains: list[NonBlankStr] = Field(
        default_factory=list,
        description="Every phrase must appear in the answer.",
    )
    contains_any: list[NonBlankStr] = Field(
        default_factory=list,
        description="At least one phrase must appear in the answer.",
    )
    numeric: float | None = Field(
        default=None,
        description="A number in the answer must equal this value.",
    )
    refusal: bool = Field(
        default=False,
        description="The answer must say the information is not available.",
    )

    @model_validator(mode="after")
    def _refusal_excludes_content(self) -> "AnswerExpectation":
        if self.refusal and (
            self.contains
            or self.contains_any
            or self.numeric is not None
        ):
            raise ValueError(
                "a refusal cannot also require answer content"
            )

        return self


class AgentEvalCase(StrictModel):
    id: NonBlankStr
    question: NonBlankStr
    expected_tools: list[ToolName] = Field(
        default_factory=list,
        description=(
            "Tools that must be called. Other tools may also be called; "
            "an empty list means no tool is required."
        ),
    )
    expected_answer: AnswerExpectation = Field(
        default_factory=AnswerExpectation,
    )
    reference_answer: NonBlankStr | None = Field(
        default=None,
        description=(
            "A correct answer the LLM correctness judge compares against. "
            "Null skips the judge (and its API call)."
        ),
    )
    grounded: bool = Field(
        default=False,
        description=(
            "The answer must come from the knowledge base: if nothing was "
            "retrieved, the answer must be a refusal (anything else is "
            "treated as a hallucination)."
        ),
    )
    expected_sources: list[NonBlankStr] | None = Field(
        default=None,
        description=(
            "Document IDs that must be among the returned sources. "
            "An empty list means no sources may be returned; null skips "
            "the check."
        ),
    )
    tags: list[NonBlankStr] = Field(default_factory=list)


class RagEvalCase(StrictModel):
    id: NonBlankStr
    query: NonBlankStr
    expected_document_id: NonBlankStr | None = Field(
        description=(
            "Document that must be retrieved, or null for a negative query "
            "that must retrieve nothing."
        ),
    )
    note: str | None = None
    tags: list[NonBlankStr] = Field(default_factory=list)


Case = TypeVar("Case", bound=StrictModel)


class DatasetError(ValueError):
    pass


def load_cases(path: Path, model: type[Case]) -> list[Case]:
    cases: list[Case] = []
    seen_ids: set[str] = set()

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            location = f"{path.name}:{line_number}"

            try:
                case = model.model_validate(json.loads(line))
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{location}: invalid JSON: {exc}") from exc
            except ValidationError as exc:
                raise DatasetError(f"{location}: {exc}") from exc

            if case.id in seen_ids:
                raise DatasetError(f"{location}: duplicate id {case.id!r}")

            seen_ids.add(case.id)
            cases.append(case)

    if not cases:
        raise DatasetError(f"{path.name}: dataset is empty")

    return cases


def load_agent_cases(path: Path = AGENT_DATASET) -> list[AgentEvalCase]:
    return load_cases(path, AgentEvalCase)


def load_rag_cases(path: Path = RAG_DATASET) -> list[RagEvalCase]:
    return load_cases(path, RagEvalCase)
