import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embedding_service import EmbeddingService


@pytest.fixture
def embedding_service():
    with patch(
        "app.services.embedding_service.GoogleGenerativeAIEmbeddings"
    ) as mock_model:
        mock_instance = MagicMock()

        mock_instance.aembed_documents = AsyncMock(
            return_value=[[0.1, 0.2, 0.3]]
        )
        mock_instance.aembed_query = AsyncMock(
            return_value=[0.4, 0.5, 0.6]
        )

        mock_model.return_value = mock_instance

        service = EmbeddingService()

        yield service, mock_instance


@pytest.mark.asyncio
async def test_embed_documents(embedding_service):
    service, mock_instance = embedding_service

    result = await service.embed_documents(
        ["FastAPI is a Python framework."]
    )

    assert result == [[0.1, 0.2, 0.3]]
    mock_instance.aembed_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_query(embedding_service):
    service, mock_instance = embedding_service

    result = await service.embed_query("What is FastAPI?")

    assert result == [0.4, 0.5, 0.6]
    mock_instance.aembed_query.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_documents(embedding_service):
    service, mock_instance = embedding_service

    result = await service.embed_documents([])

    assert result == []
    mock_instance.aembed_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_query(embedding_service):
    service, _ = embedding_service

    with pytest.raises(ValueError, match="Query cannot be empty"):
        await service.embed_query("   ")