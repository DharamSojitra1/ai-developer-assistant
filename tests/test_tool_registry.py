import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from app.agents.calculator_agent import create_agent_graph
from app.tools.registry import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_USER,
    TOOL_REGISTRY,
    ToolSpec,
    get_tools_for_role,
)


@tool
def admin_only_tool(value: str) -> str:
    """Test tool restricted to admins."""
    return value


TEST_REGISTRY = (
    *TOOL_REGISTRY,
    ToolSpec(
        tool=admin_only_tool,
        allowed_roles=frozenset({ROLE_ADMIN}),
        deterministic=True,
        side_effects="none",
    ),
)

# Every deterministic tool needs a sample input so determinism is checked.
DETERMINISM_SAMPLES = {
    "calculator": {"expression": "(10 + 5) * 2 / 3"},
    "analyze_text": {"text": "Hello world\nThis is AI"},
}


def tool_names(tools) -> set[str]:
    return {t.name for t in tools}


def test_user_gets_all_current_tools():
    assert tool_names(get_tools_for_role(ROLE_USER)) == {
        "calculator",
        "analyze_text",
        "search_knowledge_base",
        "delete_my_document",
        "web_search",
        "package_info",
    }


def test_only_document_deletion_requires_approval():
    assert {
        spec.name for spec in TOOL_REGISTRY if spec.requires_approval
    } == {"delete_my_document"}


def test_admin_only_tool_is_hidden_from_users():
    user_tools = tool_names(get_tools_for_role(ROLE_USER, TEST_REGISTRY))
    admin_tools = tool_names(get_tools_for_role(ROLE_ADMIN, TEST_REGISTRY))

    assert "admin_only_tool" not in user_tools
    assert "admin_only_tool" in admin_tools


@pytest.mark.parametrize("role", ["guest", "", None, "ADMIN", "admin "])
def test_unknown_role_gets_no_tools(role):
    assert get_tools_for_role(role) == []


def test_registry_tool_names_are_unique():
    names = [spec.name for spec in TOOL_REGISTRY]

    assert len(names) == len(set(names))


def test_registry_entries_document_behavior():
    for spec in TOOL_REGISTRY:
        assert spec.side_effects.strip(), spec.name
        assert spec.allowed_roles, spec.name
        assert spec.allowed_roles <= ALL_ROLES, spec.name


def test_non_deterministic_tools_explain_why():
    for spec in TOOL_REGISTRY:
        if not spec.deterministic:
            assert spec.side_effects != "none", spec.name


def test_deterministic_tools_return_identical_output():
    for spec in TOOL_REGISTRY:
        if not spec.deterministic:
            continue

        assert spec.name in DETERMINISM_SAMPLES, (
            f"Add a determinism sample for {spec.name}"
        )

        sample = DETERMINISM_SAMPLES[spec.name]

        assert spec.tool.invoke(sample) == spec.tool.invoke(sample)


@pytest.mark.asyncio
async def test_graph_rejects_tool_outside_role(scripted_llm):
    scripted_llm.call_tool("calculator", expression="1 + 1").answer(
        "Cannot do that."
    )

    result = await create_agent_graph(role="guest").ainvoke(
        {"messages": [("human", "What is 1 + 1?")]}
    )

    tool_message = next(
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage)
    )

    assert tool_message.status == "error"
    assert "not a valid tool" in tool_message.content
    assert result["tool_calls"][0]["status"] == "error"
