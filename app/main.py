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
from app.config import FRONTEND_URL, DEBUG
from app.exceptions import app_exception_handler
from app.custom_exceptions import AppException
from app.middleware import request_id_middleware
from contextlib import asynccontextmanager

logger = logging.getLogger()

handler = logging.StreamHandler()
handler.setFormatter(
    JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
)

logger.handlers.clear()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongodb()

    yield

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
]
)

app.middleware("http")(request_id_middleware)
app.add_exception_handler(
    AppException,
    app_exception_handler
)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
) 

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET","POST"],
    allow_headers=["Content-Type", "Authorization"]
)

app.include_router(chat_router,prefix="/api/chat")


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