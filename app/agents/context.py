"""Shrink what the agent LLM sees of earlier search results.

Every LLM step re-sends the whole message list, so without this each extra
search makes all later steps pay again for every earlier result. Only the
LLM input is changed; the graph state keeps the full results, so sources
are unaffected.
"""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from app.tools.tool_result import parse_tool_result, tool_success

COMPACTABLE_TOOLS = frozenset({"search_knowledge_base", "web_search"})

COMPACTED_NOTE = (
    "Full text omitted to save tokens; you already read these results in an "
    "earlier step. Cite them by document_id if you used them."
)


def _latest_tool_call_index(messages: Sequence[BaseMessage]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]

        if isinstance(message, AIMessage) and message.tool_calls:
            return index

    return None


def _compacted(message: ToolMessage) -> ToolMessage:
    payload = parse_tool_result(message.content)

    if payload is None or not payload["ok"]:
        return message

    references = []

    for result in (payload["result"] or {}).get("results", []):
        reference = {"document_id": result.get("document_id")}

        if result.get("title"):
            reference["title"] = result["title"]

        references.append(reference)

    return message.model_copy(
        update={
            "content": tool_success(
                {"compacted": True, "note": COMPACTED_NOTE, "results": references}
            )
        }
    )


def compact_tool_context(
    messages: Sequence[BaseMessage],
    budget_chars: int,
) -> list[BaseMessage]:
    """Older search results beyond `budget_chars`, reduced to references.

    Results of the latest tool step are always kept in full. Walking back
    from there, search results stay in full while their combined size fits
    the budget; that one and everything older is compacted.
    """
    messages = list(messages)
    latest = _latest_tool_call_index(messages)

    if latest is None:
        return messages

    used = 0
    over_budget = False

    for index in range(latest - 1, -1, -1):
        message = messages[index]

        if not (
            isinstance(message, ToolMessage)
            and message.name in COMPACTABLE_TOOLS
        ):
            continue

        if not over_budget:
            used += len(str(message.content))
            over_budget = used > budget_chars

        if over_budget:
            messages[index] = _compacted(message)

    return messages
