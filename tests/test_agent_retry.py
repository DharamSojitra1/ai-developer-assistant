from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.calculator_agent import invoke_agent_llm


@pytest.mark.asyncio
async def test_agent_llm_retries_on_connection_error():
    llm = Mock()

    llm.ainvoke = AsyncMock(
        side_effect=[
            ConnectionError("temporary failure"),
            ConnectionError("temporary failure"),
            "success",
        ]
    )

    result = await invoke_agent_llm(
        llm,
        ["test message"],
    )

    assert result == "success"
    assert llm.ainvoke.call_count == 3
