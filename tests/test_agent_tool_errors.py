from unittest.mock import patch

import pytest

from app.agents.calculator_agent import create_agent_graph


@pytest.mark.asyncio
async def test_agent_handles_tool_error():
    graph = create_agent_graph(
        temperature=0,
        max_tokens=500,
    )

    with patch(
        "app.agents.calculator_agent.calculator",
    ) as mock_calculator:
        mock_calculator.invoke.side_effect = RuntimeError(
            "calculator failed"
        )

        result = await graph.ainvoke(
            {
                "messages": [
                    (
                        "human",
                        "Calculate 25 * 4",
                    )
                ],
                "iteration_count": 0,
                "sources": [],
            }
        )

    assert result["messages"]