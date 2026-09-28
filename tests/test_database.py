import pytest

from app.database import connect_to_mongodb


@pytest.mark.asyncio
async def test_mongodb_connection():
    await connect_to_mongodb()  