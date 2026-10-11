"""Where agent graphs store their checkpoints.

Each run is its own thread (`thread_id = run_id`): conversation memory stays
in `chat_history`, and checkpoints only make a run resumable (approval
pauses) and inspectable. The app lifespan installs a MongoDB saver; until
then (and in tests) runs use an in-memory saver.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from app.config import (
    AGENT_CHECKPOINT_TTL_SECONDS,
    MONGODB_DATABASE,
    MONGODB_URI,
)

CHECKPOINT_COLLECTION = "agent_checkpoints"
WRITES_COLLECTION = "agent_checkpoint_writes"

_checkpointer: BaseCheckpointSaver | None = None


def get_checkpointer() -> BaseCheckpointSaver:
    global _checkpointer

    if _checkpointer is None:
        _checkpointer = InMemorySaver()

    return _checkpointer


def set_checkpointer(saver: BaseCheckpointSaver | None) -> None:
    global _checkpointer
    _checkpointer = saver


def run_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def create_mongo_checkpointer(
    uri: str = MONGODB_URI,
    db_name: str = MONGODB_DATABASE,
    ttl: int | None = AGENT_CHECKPOINT_TTL_SECONDS,
) -> MongoDBSaver:
    """MongoDB saver; blocking (connects and creates indexes), so run it in
    a thread. The caller closes `saver.client` on shutdown."""
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    try:
        return MongoDBSaver(
            client,
            db_name=db_name,
            checkpoint_collection_name=CHECKPOINT_COLLECTION,
            writes_collection_name=WRITES_COLLECTION,
            ttl=ttl,
        )
    except Exception:
        client.close()
        raise
