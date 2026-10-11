from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableLambda

from app.services import chat_service


@pytest.mark.asyncio
async def test_generate_response_mock_mode(monkeypatch):
    monkeypatch.setattr(chat_service, "MOCK_MODE", True)

    result = await chat_service.generate_response(
        message="Hello",
        temperature=0.7,
        max_tokens=1024,
        user_id="user-1",
    )

    assert result == {"response": "Mock response: Hello", "sources": []}


@pytest.mark.asyncio
async def test_generate_response_llm_mode(monkeypatch):
    monkeypatch.setattr(chat_service, "MOCK_MODE", False)

    rag_service = MagicMock()
    rag_service.retrieve = AsyncMock(
        return_value=[
            {
                "text": "FastAPI is a Python framework.",
                "metadata": {"document_id": "doc-1"},
            }
        ]
    )
    monkeypatch.setattr(chat_service, "RAGService", lambda: rag_service)

    monkeypatch.setattr(
        chat_service,
        "get_recent_chat_history",
        AsyncMock(
            return_value=[{"message": "Hi", "response": "Hello!"}]
        ),
    )

    chain_inputs = []

    def fake_chain(inputs):
        chain_inputs.append(inputs)
        return "Hello from AI"

    create_rag_chain = MagicMock(return_value=RunnableLambda(fake_chain))
    monkeypatch.setattr(chat_service, "create_rag_chain", create_rag_chain)

    result = await chat_service.generate_response(
        message="What is FastAPI?",
        temperature=0.7,
        max_tokens=1024,
        user_id="user-1",
    )

    assert result == {
        "response": "Hello from AI",
        "sources": [
            {
                "document_id": "doc-1",
                "text": "FastAPI is a Python framework.",
            }
        ],
    }

    create_rag_chain.assert_called_once_with(
        temperature=0.7,
        max_tokens=1024,
    )
    rag_service.retrieve.assert_awaited_once_with(
        query="What is FastAPI?",
        top_k=3,
        user_id="user-1",
    )

    assert chain_inputs[0]["context"] == (
        '<document id="doc-1">\nFastAPI is a Python framework.\n</document>'
    )
    assert chain_inputs[0]["chat_history"] == [
        ("human", "Hi"),
        ("ai", "Hello!"),
    ]
