from unittest.mock import Mock

import pytest

from app.agents.calculator_agent import invoke_agent_llm


def test_agent_llm_retries_on_connection_error():
    llm = Mock()

    llm.invoke.side_effect = [
        ConnectionError("temporary failure"),
        ConnectionError("temporary failure"),
        "success",
    ]

    result = invoke_agent_llm(
        llm,
        ["test message"],
    )

    assert result == "success"
    assert llm.invoke.call_count == 3