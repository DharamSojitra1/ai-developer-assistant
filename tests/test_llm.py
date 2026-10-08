from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from groq import APITimeoutError

from app.services import llm_service


def make_timeout_error():
    return APITimeoutError(
        request=httpx.Request("POST", "https://api.groq.com")
    )


@pytest.mark.anyio
async def test_retry_success(monkeypatch):
    mock_ainvoke = AsyncMock(
        side_effect=[
            make_timeout_error(),
            make_timeout_error(),
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
        "ChatGroq",
        FakeLLM,
    )

    result = await llm_service.generate_ai_response(
        message="Hello",
        temperature=0.7,
        max_tokens=100,
    )

    assert result == "Success"
    assert mock_ainvoke.await_count == 3
