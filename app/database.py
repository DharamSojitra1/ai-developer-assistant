from langchain_core.runnables import history
from filetype.types import document
from pymongo.common import clean_node
from pymongo import AsyncMongoClient
from app.config import MONGODB_URI, MONGODB_DATABASE
from datetime import datetime, timezone

client = AsyncMongoClient(MONGODB_URI)
database = client[MONGODB_DATABASE]

async def connect_to_mongodb():
    await client.admin.command("ping")
    print("MongoDB Connected Successfully")

async def close_mongodb_connection():
    await client.close()


async def save_chat_history(
    message: str,
    response: str,
    model: str,
):
    document = {
        "message":message,
        "response": response,
        "model": model,
        "created_at": datetime.now(timezone.utc),
    }

    result = await database["chat_history"].insert_one(document)

    return result.inserted_id

async def get_chat_history(
    limit: int = 20,
    skip: int = 0
):
    cursor = (
        database["chat_history"]
        .find({})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    history = await cursor.to_list(length=limit)

    for item in history:
        item["_id"] = str(item["_id"])

    return history