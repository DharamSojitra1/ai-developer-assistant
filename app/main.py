import asyncio

from app.database import (
    create_chat_history_indexes,
    create_token_usage_index,
    create_users_index,
)
from app.database import close_mongodb_connection
from app.database import connect_to_mongodb
from fastapi import FastAPI
from app.routes.chat import router as chat_router
import logging
from pythonjsonlogger.json import JsonFormatter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import ConnectionFailure
from app.config import (
    FRONTEND_URL,
    DEBUG,
    MAX_REQUEST_BYTES,
    MOCK_MODE,
    ENABLE_RERANKER,
)
from groq import RateLimitError
from app.exceptions import (
    app_exception_handler,
    database_unavailable_handler,
    model_rate_limited_handler,
    unhandled_exception_handler,
)
from app.custom_exceptions import AppException
from app.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from app.utils.log_context import LogContextFilter
from app.utils.redaction import RedactionFilter
from contextlib import asynccontextmanager
from app.routes import auth
from app.routes import rag
from app.routes import agent
from app.routes import usage
from app.services.chat_service import get_rag_service
from app.services.embedding_migration import pending_chunk_count
from app.services.vector_store_service import VectorStoreService
from app.agents.checkpoints import create_mongo_checkpointer, set_checkpointer

logger = logging.getLogger()

handler = logging.StreamHandler()
handler.setFormatter(
    JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
)
handler.addFilter(LogContextFilter())
handler.addFilter(RedactionFilter())

logger.handlers.clear()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def warn_about_stale_embeddings() -> None:
    pending = pending_chunk_count(VectorStoreService())

    if pending:
        logger.warning(
            "Chunks embedded with a previous model are not searchable; "
            "run `python -m app.scripts.reembed`",
            extra={"pending_chunks": pending},
        )


async def open_agent_checkpointer():
    """Store agent checkpoints in MongoDB; keep in-memory ones if it fails.

    In memory, runs paused for approval are lost on restart.
    """
    try:
        saver = await asyncio.to_thread(create_mongo_checkpointer)
    except Exception as exc:
        logger.warning(
            "MongoDB agent checkpoints unavailable; using in-memory ones",
            extra={"error_type": type(exc).__name__},
        )
        return None

    set_checkpointer(saver)
    return saver


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongodb()
    await create_users_index()
    await create_token_usage_index()
    await create_chat_history_indexes()
    await asyncio.to_thread(warn_about_stale_embeddings)
    saver = await open_agent_checkpointer()

    if not MOCK_MODE and ENABLE_RERANKER:
        # Load the reranker now so the first chat message doesn't wait for it.
        await asyncio.to_thread(get_rag_service)

    yield

    if saver is not None:
        set_checkpointer(None)
        saver.client.close()

    await close_mongodb_connection()


app = FastAPI(
    title="AI Developer Assistant API",
    description="""
    AI-powered developer assistant API.

    Features:
    - AI chat responses
    - API key authentication
    - Request validation
    - Rate limiting
    """,
    version="1.0.0",
    lifespan=lifespan,
    debug=DEBUG,
    contact={
        "name": "Dharam",
        "url": "https://github.com/DharamSojitra1/ai-developer-assistant",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
    {
        "name": "Chat",
        "description": "AI chat and response generation endpoints.",
    },
    {
        "name": "RAG",
        "description": "Retrieval-Augmented Generation endpoints.",
    },
]
)

# Inside the request-ID middleware, so rejected bodies are still logged.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)
app.add_middleware(RequestIdMiddleware)
app.add_exception_handler(
    AppException,
    app_exception_handler
)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
) 
app.add_exception_handler(
    ConnectionFailure,
    database_unavailable_handler
)
app.add_exception_handler(
    RateLimitError,
    model_rate_limited_handler
)
app.add_exception_handler(
    Exception,
    unhandled_exception_handler
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"]
)

app.include_router(chat_router,prefix="/api/chat",tags=["Chat"])
app.include_router(
    auth.router,
    prefix="/api/auth",
    tags=["Authentication"],
)
app.include_router(
    rag.router,
    prefix="/api/rag",
    tags=["RAG"],
)
app.include_router(
    agent.router,
    prefix="/api",
    tags=["Agent"],
)
app.include_router(
    usage.router,
    prefix="/api",
)

@app.get("/")
async def root():
    return {"message": "AI Developer Assistant API"}

@app.get("/health")
async def health():
    logger.info("Health check requested")
    return {"status": "healthy"}

@app.get("/test-error")
async def test_error():
    raise AppException(
        message="Resource not found",
        status_code=404,
        error_code="RESOURCE_NOT_FOUND",
    )