from types import SimpleNamespace
from unittest.mock import AsyncMock
from google.api_core.exceptions import ServiceUnavailable

import pytest

from app.services import llm_service


@pytest.mark.anyio
async def test_retry_success(monkeypatch):
    mock_ainvoke = AsyncMock(
        side_effect=[
            ServiceUnavailable("Temporary error"),
            ServiceUnavailable("Temporary error"),
            SimpleNamespace(text="Success"),
        ]
    )

    class FakeLLM:
        def __init__(self, **kwargs):
            pass

        async def ainvoke(self, message):
            return await mock_ainvoke(message)

    monkeypatch.setattr(
        llm_service,
        "ChatGoogleGenerativeAI",
        FakeLLM,
    )

    result = await llm_service.generate_ai_response(
        message="Hello",
        temperature=0.7,
        max_tokens=100,
    )

    assert result == "Success"
    assert mock_ainvoke.await_count == 3