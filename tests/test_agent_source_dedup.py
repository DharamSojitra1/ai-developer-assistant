from langchain_core.messages import ToolMessage

from app.agents.calculator_agent import collect_sources
from app.tools.tool_result import tool_error, tool_success


def test_collect_sources_removes_duplicate_sources():
    state = {
        "messages": [],
        "iteration_count": 0,
        "sources": [
            {
                "document_id": "doc-1",
                "text": "Generative AI is AI that generates content."
            }
        ],
    }

    result = collect_sources(state)

    assert len(result["sources"]) == 1


def test_collect_sources_reads_structured_tool_results():
    source = {"document_id": "doc-1", "text": "Some text"}

    state = {
        "messages": [
            ToolMessage(
                content=tool_success({"results": [source, source]}),
                name="search_knowledge_base",
                tool_call_id="call-1",
            ),
            ToolMessage(
                content=tool_error("Knowledge base search failed."),
                name="search_knowledge_base",
                tool_call_id="call-2",
            ),
        ],
        "sources": [],
    }

    result = collect_sources(state)

    assert result["sources"] == [source]
