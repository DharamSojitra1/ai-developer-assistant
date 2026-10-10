
from unittest.mock import AsyncMock

import pytest

from app.services.answerability_service import (
    AnswerabilityResult,
    AnswerabilityService,
)


@pytest.fixture
def service():
    instance = AnswerabilityService.__new__(AnswerabilityService)
    instance.chain = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_evaluate_returns_answerable_result(service):
    expected = AnswerabilityResult(
        is_answerable=True,
        reason="The context defines FastAPI and its main features.",
    )
    service.chain.ainvoke.return_value = expected

    result = await service.evaluate(
        query="What is FastAPI?",
        context=(
            "FastAPI is a Python web framework that provides "
            "automatic OpenAPI documentation."
        ),
    )

    assert result.is_answerable is True
    assert "FastAPI" in result.reason
    service.chain.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_returns_unanswerable_result(service):
    expected = AnswerabilityResult(
        is_answerable=False,
        reason="The context does not explain song composition.",
    )
    service.chain.ainvoke.return_value = expected

    result = await service.evaluate(
        query="How can I use Generative AI to compose a song?",
        context=(
            "Generative AI can generate new content such as "
            "text, images, audio, video, and code."
        ),
    )

    assert result.is_answerable is False
    service.chain.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_rejects_empty_query(service):
    with pytest.raises(ValueError, match="Query cannot be empty"):
        await service.evaluate(
            query="   ",
            context="Some context",
        )

    service.chain.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluate_rejects_empty_context_without_llm_call(service):
    result = await service.evaluate(
        query="What is FastAPI?",
        context="   ",
    )

    assert result.is_answerable is False
    assert "No reference context" in result.reason
    service.chain.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluate_propagates_llm_failure(service):
    service.chain.ainvoke.side_effect = RuntimeError(
        "Evaluator unavailable"
    )

    with pytest.raises(RuntimeError, match="Evaluator unavailable"):
        await service.evaluate(
            query="What is FastAPI?",
            context="FastAPI is a Python web framework.",
        )


@pytest.mark.asyncio
async def test_evaluate_propagates_llm_failure(service):
    service.chain.ainvoke.side_effect = RuntimeError(
        "Evaluator unavailable"
    )

    with pytest.raises(RuntimeError, match="Evaluator unavailable"):
        await service.evaluate(
            query="How can I use Generative AI to compose a song?",
            context=(
                "Generative AI can generate text, images, "
                "audio, video, and code."
            ),
        )

    service.chain.ainvoke.assert_awaited_once()
