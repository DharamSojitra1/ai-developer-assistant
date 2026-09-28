import pytest
from pymongo import AsyncMongoClient
from app.config import MONGODB_URI


@pytest.mark.asyncio
async def test_mongodb_connection():
    async with AsyncMongoClient(MONGODB_URI) as test_client:
        result = await test_client.admin.command("ping")

        assert result["ok"] == 1