from app.agents.calculator_agent import collect_sources


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