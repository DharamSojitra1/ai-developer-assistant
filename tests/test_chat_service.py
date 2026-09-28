from unittest.mock import AsyncMock

import pytest

from app.services import chat_service


@pytest.mark.asyncio
async def test_generate_response_mock_mode(monkeypatch):
    monkeypatch.setattr(chat_service, "MOCK_MODE", True)

    result = await chat_service.generate_response(
        message="Hello",
        temperature=0.7,
        max_tokens=1024,
    )

    assert result == "Mock response: Hello"


@pytest.mark.asyncio
async def test_generate_response_llm_mode(monkeypatch):
    monkeypatch.setattr(chat_service, "MOCK_MODE", False)

    mock_llm = AsyncMock(return_value="Hello from AI")

    monkeypatch.setattr(
        chat_service,
        "generate_ai_response",
        mock_llm,
    )

    result = await chat_service.generate_response(
        message="Hello",
        temperature=0.7,
        max_tokens=1024,
    )

    assert result == "Hello from AI"

    mock_llm.assert_awaited_once_with(
        "Hello",
        0.7,
        1024,
    )