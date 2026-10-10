from pymongo import AsyncMongoClient, ReturnDocument
from app.config import MONGODB_URI, MONGODB_DATABASE
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

client = AsyncMongoClient(MONGODB_URI)
database = client[MONGODB_DATABASE]

async def connect_to_mongodb():
    await client.admin.command("ping")
    print("MongoDB Connected Successfully")

async def close_mongodb_connection():
    await client.close()


async def save_chat_history(
    user_id: str,
    message: str,
    response: str,
    model: str,
):
    document = {
        "user_id": user_id,
        "message": message,
        "response": response,
        "model": model,
        "created_at": datetime.now(timezone.utc),
    }

    result = await database["chat_history"].insert_one(document)

    return result.inserted_id

async def get_chat_history(
    user_id: str,
    limit: int = 20,
    skip: int = 0,
):
    cursor = (
        database["chat_history"]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    history = await cursor.to_list(length=limit)

    for item in history:
        item["id"] = str(item.pop("_id"))

    return history

async def create_users_index():
    await database["users"].create_index(
        "email",
        unique=True,
    )


async def create_user(email: str, hashed_password: str):
    document = {
        "email": email.lower(),
        "hashed_password": hashed_password,
    }

    try:
        result = await database["users"].insert_one(document)

        return {
            "id": str(result.inserted_id),
            "email": document["email"],
        }

    except DuplicateKeyError:
        return None

async def get_user_by_email(email: str):
    return await database["users"].find_one(
        {"email": email.lower()}
    )

async def get_user_by_id(user_id: str):
    if not ObjectId.is_valid(user_id):
        return None

    return await database["users"].find_one(
        {"_id": ObjectId(user_id)}
    )


async def save_refresh_token(
    user_id: str,
    token_hash: str,
    expires_at: datetime,
):
    document = {
        "user_id": user_id,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "revoked": False,
        "created_at": datetime.now(timezone.utc),
    }

    result = await database["refresh_tokens"].insert_one(
        document
    )

    return str(result.inserted_id)

async def revoke_refresh_token(token_hash: str):
    return await database["refresh_tokens"].find_one_and_update(
        {
            "token_hash": token_hash,
            "revoked": False,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {"$set": {"revoked": True}},
        return_document=ReturnDocument.BEFORE,
    )

async def get_recent_chat_history(
    user_id: str,
    limit: int = 10,
):
    cursor = (
        database["chat_history"]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )

    history = await cursor.to_list(length=limit)

    for item in history:
        item["id"] = str(item.pop("_id"))

    history.reverse()

    return history