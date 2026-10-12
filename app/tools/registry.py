from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from langchain_core.tools import BaseTool

from app.tools.calculator import calculator
from app.tools.delete_document import delete_my_document, describe_delete_request
from app.tools.package_info import package_info
from app.tools.rag_search import search_knowledge_base
from app.tools.text_analyzer import analyze_text
from app.tools.web_search import web_search


ROLE_USER = "user"
ROLE_ADMIN = "admin"

ALL_ROLES = frozenset({ROLE_USER, ROLE_ADMIN})

# Builds the summary a user sees when asked to approve a call, from its args.
ApprovalDescriber = Callable[[dict], Awaitable[dict]]


@dataclass(frozen=True)
class ToolSpec:
    tool: BaseTool
    allowed_roles: frozenset[str]
    deterministic: bool
    # "none", or a description of what the tool touches outside itself.
    side_effects: str
    # Sensitive tools pause the agent until the user approves the call.
    describe_approval: ApprovalDescriber | None = None

    @property
    def name(self) -> str:
        return self.tool.name

    @property
    def requires_approval(self) -> bool:
        return self.describe_approval is not None


TOOL_REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        tool=calculator,
        allowed_roles=ALL_ROLES,
        deterministic=True,
        side_effects="none",
    ),
    ToolSpec(
        tool=analyze_text,
        allowed_roles=ALL_ROLES,
        deterministic=True,
        side_effects="none",
    ),
    ToolSpec(
        tool=search_knowledge_base,
        allowed_roles=ALL_ROLES,
        deterministic=False,
        side_effects=(
            "Read-only; calls the embedding API and an LLM "
            "(answerability check), which cost money and may vary."
        ),
    ),
    ToolSpec(
        tool=delete_my_document,
        allowed_roles=ALL_ROLES,
        deterministic=False,
        side_effects=(
            "Permanently deletes one of the user's own knowledge-base "
            "documents."
        ),
        describe_approval=describe_delete_request,
    ),
    ToolSpec(
        tool=web_search,
        allowed_roles=ALL_ROLES,
        deterministic=False,
        side_effects=(
            "Read-only; calls the paid Tavily search API (cached briefly). "
            "Returns untrusted web content."
        ),
    ),
    ToolSpec(
        tool=package_info,
        allowed_roles=ALL_ROLES,
        deterministic=False,
        side_effects=(
            "Read-only; calls the free public PyPI or npm registry API."
        ),
    ),
)


def get_tools_for_role(
    role: str | None,
    registry: tuple[ToolSpec, ...] = TOOL_REGISTRY,
) -> list[BaseTool]:
    """Return the tools a role may use; unknown roles get none."""
    return [
        spec.tool
        for spec in registry
        if role in spec.allowed_roles
    ]


def approval_describers(
    tools: Sequence[BaseTool],
    registry: tuple[ToolSpec, ...] = TOOL_REGISTRY,
) -> dict[str, ApprovalDescriber]:
    """Tool name -> approval describer, for the given tools that need approval."""
    names = {tool.name for tool in tools}

    return {
        spec.name: spec.describe_approval
        for spec in registry
        if spec.requires_approval and spec.name in names
    }
