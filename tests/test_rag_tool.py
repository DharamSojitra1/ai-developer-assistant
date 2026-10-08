import pytest

from app.tools.rag_search import search_knowledge_base


@pytest.mark.asyncio
async def test_rag_search_tool():
    result = await search_knowledge_base.ainvoke(
        {
            "query": "What is Generative AI?"
        }
    )

    print("\nRAG TOOL RESULT:")
    print(result)

    assert isinstance(result, str)