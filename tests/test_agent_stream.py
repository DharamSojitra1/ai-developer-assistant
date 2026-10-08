import re
from uuid import uuid4

import pytest

from app.agents.agent_service import stream_agent_response


@pytest.mark.asyncio
async def test_agent_stream_text(async_test_db):
    chunks = []

    async for chunk in stream_agent_response(
        user_id=f"test-user-{uuid4()}",
        message="What is 25 * 4?",
    ):
        chunks.append(chunk)

    full_response = "".join(chunks)

    print("\nFULL RESPONSE:")
    print(full_response)

    assert chunks
    assert all(isinstance(chunk, str) for chunk in chunks)

    # LLMs may format numbers as "100" or with narrow spaces.
    assert "100" in re.sub(r"[\s,]", "", full_response)

    # The calculator's raw output must not leak into the streamed answer.
    assert not full_response.startswith("100")
