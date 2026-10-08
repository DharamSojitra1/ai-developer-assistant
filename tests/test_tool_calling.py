import re

import pytest

from langchain_core.messages import ToolMessage

from app.services.tool_llm_service import create_tool_llm
from app.tools.calculator import calculator


@pytest.mark.asyncio
async def test_complete_tool_calling_loop():
    llm = create_tool_llm(
        temperature=0,
        max_tokens=100,
    )

    user_message = "What is 125 * 48?"

    # 1. Ask the LLM
    response = await llm.ainvoke(user_message)

    assert response.tool_calls

    tool_call = response.tool_calls[0]

    # 2. Execute the tool
    tool_result = calculator.invoke(
        tool_call["args"]
    )

    assert tool_result == "6000"

    # 3. Create a ToolMessage
    tool_message = ToolMessage(
        content=tool_result,
        tool_call_id=tool_call["id"],
    )

    # 4. Send the original AI response + tool result back to the LLM
    final_response = await llm.ainvoke(
        [
            ("human", user_message),
            response,
            tool_message,
        ]
    )

    print("\nFINAL RESPONSE:")
    print(final_response.content)

    assert final_response.content

    # LLMs may format numbers as "6000", "6,000" or with narrow spaces.
    normalized = re.sub(r"[\s,]", "", final_response.content)
    assert "6000" in normalized