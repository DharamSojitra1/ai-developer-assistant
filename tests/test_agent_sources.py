import pytest

from app.agents.calculator_agent import create_agent_graph


@pytest.mark.asyncio
async def test_agent_state_contains_rag_sources():
    graph = create_agent_graph(
        temperature=0,
        max_tokens=500,
    )

    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "According to the knowledge base, "
                    "what is Generative AI?"
                )
            ],
            "iteration_count": 0,
            "sources": [],
        }
    )

    print("\nAGENT SOURCES:")
    print(result.get("sources"))

    sources = result.get("sources", [])

    assert sources
    assert sources[0]["document_id"] == "gen-ai-basics"
    assert "Generative AI" in sources[0]["text"]