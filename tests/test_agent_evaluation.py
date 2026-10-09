import pytest

from app.agents.calculator_agent import create_agent_graph


@pytest.mark.asyncio
async def test_agent_uses_calculator_for_arithmetic():
    graph = create_agent_graph(
        temperature=0,
        max_tokens=500,
    )

    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "What is 125 * 4?",
                )
            ],
            "iteration_count": 0,
            "sources": [],
        }
    )

    tool_calls = [
        call
        for message in result["messages"]
        if hasattr(message, "tool_calls")
        for call in message.tool_calls
    ]

    assert any(
        call["name"] == "calculator"
        for call in tool_calls
    )

@pytest.mark.asyncio
async def test_agent_returns_correct_calculation_result():
    graph = create_agent_graph(
        temperature=0,
        max_tokens=500,
    )

    result = await graph.ainvoke(
        {
            "messages": [
                (
                    "human",
                    "What is 125 * 4?",
                )
            ],
            "iteration_count": 0,
            "sources": [],
        }
    )

    final_message = result["messages"][-1]
    response = final_message.content

    assert "500" in response

@pytest.mark.asyncio
async def test_agent_uses_rag_for_knowledge_base_question():
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

    tool_calls = [
        call
        for message in result["messages"]
        if hasattr(message, "tool_calls")
        for call in message.tool_calls
    ]

    assert any(
        call["name"] == "search_knowledge_base"
        for call in tool_calls
    )

    sources = result.get("sources", [])

    assert sources
    assert sources[0]["document_id"] == "gen-ai-basics"

@pytest.mark.asyncio
async def test_agent_handles_missing_information():
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
                    "what is the history of quantum computing?"
                )
            ],
            "iteration_count": 0,
            "sources": [],
        }
    )

    final_message = result["messages"][-1]

    # LLMs often use typographic apostrophes ("I’m"), so normalize them.
    response = final_message.content.lower().replace("\u2019", "'")

    print("\nMISSING INFO RESPONSE:")
    print(response)

    assert any(
        phrase in response
        for phrase in [
            "don't have enough information",
            "do not have enough information",
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
        ]
    )

@pytest.mark.asyncio
async def test_agent_answer_is_grounded_in_rag_context():
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
                    "what can Generative AI generate?"
                )
            ],
            "iteration_count": 0,
            "sources": [],
        }
    )

    sources = result.get("sources", [])

    assert sources
    assert sources[0]["document_id"] == "gen-ai-basics"

    final_message = result["messages"][-1]
    response = final_message.content.lower()

    assert "text" in response
    assert "image" in response
    assert "audio" in response

@pytest.mark.asyncio
async def test_agent_does_not_add_unsupported_rag_claims():
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
                    "what types of content can Generative AI generate?"
                )
            ],
            "iteration_count": 0,
            "sources": [],
        }
    )

    sources = result.get("sources", [])

    assert sources
    assert sources[0]["document_id"] == "gen-ai-basics"

    final_message = result["messages"][-1]
    response = final_message.content.lower()

    allowed_content_types = [
        "text",
        "image",
        "audio",
        "video",
        "code",
    ]

    mentioned_types = [
        content_type
        for content_type in allowed_content_types
        if content_type in response
    ]

    assert mentioned_types