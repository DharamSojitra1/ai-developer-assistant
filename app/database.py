import uuid

from pymongo import AsyncMongoClient, ReturnDocument
from app.config import CHAT_HISTORY_RETENTION_DAYS, MONGODB_URI, MONGODB_DATABASE
from datetime import date, datetime, timedelta, timezone
from pymongo.errors import DuplicateKeyError, OperationFailure

# IndexOptionsConflict, IndexKeySpecsConflict
INDEX_OPTIONS_CONFLICT_CODES = {85, 86}
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
    conversation_id: str | None = None,
):
    document = {
        "user_id": user_id,
        "conversation_id": conversation_id or str(uuid.uuid4()),
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
        "role": "user",
    }

    try:
        result = await database["users"].insert_one(document)

        return {
            "id": str(result.inserted_id),
            "email": document["email"],
            "role": document["role"],
        }

    except DuplicateKeyError:
        return None

async def get_user_by_email(email: str):
    return await database["users"].find_one(
        {"email": email.lower()}
    )

async def set_user_role(email: str, role: str) -> bool:
    if role not in {"user", "admin"}:
        raise ValueError("Invalid user role")

    result = await database["users"].update_one(
        {"email": email.lower()},
        {"$set": {"role": role}},
    )

    return result.matched_count == 1

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
    conversation_id: str | None = None,
):
    """The user's latest turns, oldest first.

    With a conversation ID only that conversation's turns are used; without
    one, the user's latest turns across all conversations.
    """
    query = {"user_id": user_id}

    if conversation_id is not None:
        query["conversation_id"] = conversation_id

    cursor = (
        database["chat_history"]
        .find(query)
        .sort("created_at", -1)
        .limit(limit)
    )

    history = await cursor.to_list(length=limit)

    for item in history:
        item["id"] = str(item.pop("_id"))

    history.reverse()

    return history


CONVERSATION_TITLE_CHARS = 80


async def list_conversations(
    user_id: str,
    limit: int = 20,
    skip: int = 0,
) -> list[dict]:
    """The user's conversations, most recently active first."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$sort": {"created_at": 1}},
        {
            "$group": {
                "_id": "$conversation_id",
                "title": {"$first": "$message"},
                "message_count": {"$sum": 1},
                "created_at": {"$first": "$created_at"},
                "updated_at": {"$last": "$created_at"},
            }
        },
        {"$sort": {"updated_at": -1, "_id": 1}},
        {"$skip": skip},
        {"$limit": limit},
    ]

    cursor = await database["chat_history"].aggregate(pipeline)
    conversations = await cursor.to_list(length=limit)

    for item in conversations:
        item["id"] = str(item.pop("_id"))
        item["title"] = item["title"][:CONVERSATION_TITLE_CHARS]

    return conversations


async def get_conversation(
    user_id: str,
    conversation_id: str,
) -> list[dict] | None:
    """Every turn of one of the user's conversations, oldest first."""
    cursor = (
        database["chat_history"]
        .find({"user_id": user_id, "conversation_id": conversation_id})
        .sort("created_at", 1)
    )

    messages = await cursor.to_list(length=None)

    if not messages:
        return None

    for item in messages:
        item["id"] = str(item.pop("_id"))

    return messages


async def delete_conversation(user_id: str, conversation_id: str) -> int:
    result = await database["chat_history"].delete_many(
        {"user_id": user_id, "conversation_id": conversation_id}
    )
    return result.deleted_count


CHAT_HISTORY_TTL_INDEX = "chat_history_retention"


async def create_chat_history_indexes(
    retention_days: int = CHAT_HISTORY_RETENTION_DAYS,
):
    """History lookup index, plus a TTL index that deletes old turns.

    MongoDB refuses to change an existing index's options, so a changed
    retention period is applied with `collMod` instead.
    """
    collection = database["chat_history"]
    ttl_seconds = retention_days * 24 * 3600

    await collection.create_index([("user_id", 1), ("created_at", -1)])
    await collection.create_index(
        [("user_id", 1), ("conversation_id", 1), ("created_at", 1)]
    )

    # Turns saved before conversations existed each become their own
    # conversation; once backfilled, this matches nothing.
    await collection.update_many(
        {"conversation_id": {"$exists": False}},
        [{"$set": {"conversation_id": {"$toString": "$_id"}}}],
    )

    try:
        await collection.create_index(
            "created_at",
            name=CHAT_HISTORY_TTL_INDEX,
            expireAfterSeconds=ttl_seconds,
        )
    except OperationFailure as exc:
        if exc.code not in INDEX_OPTIONS_CONFLICT_CODES:
            raise

        await database.command(
            "collMod",
            "chat_history",
            index={
                "name": CHAT_HISTORY_TTL_INDEX,
                "expireAfterSeconds": ttl_seconds,
            },
        )


async def delete_chat_history(user_id: str) -> int:
    result = await database["chat_history"].delete_many({"user_id": user_id})
    return result.deleted_count


async def create_token_usage_index():
    await database["token_usage"].create_index(
        [("user_id", 1), ("date", 1)],
        unique=True,
    )


async def record_token_usage(
    user_id: str,
    llm_calls: int,
    input_tokens: int,
    output_tokens: int,
    day: date | None = None,
):
    """Add one request's LLM usage to the user's daily (UTC) totals."""
    day = day or datetime.now(timezone.utc).date()

    await database["token_usage"].update_one(
        {"user_id": user_id, "date": day.isoformat()},
        {
            "$inc": {
                "requests": 1,
                "llm_calls": llm_calls,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )


async def get_token_usage(user_id: str, days: int = 30) -> list[dict]:
    """Daily usage for the last ``days`` UTC days (today included), newest first."""
    since = datetime.now(timezone.utc).date() - timedelta(days=days - 1)

    cursor = (
        database["token_usage"]
        .find(
            {"user_id": user_id, "date": {"$gte": since.isoformat()}},
            {"_id": 0, "user_id": 0, "updated_at": 0},
        )
        .sort("date", -1)
    )

    return await cursor.to_list(length=days)