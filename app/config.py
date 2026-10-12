from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Populates os.environ for libraries that read keys directly from the
# environment (e.g. the Google embeddings client reads GEMINI_API_KEY).
load_dotenv()

# Values shipped in .env.example; never acceptable in production.
PLACEHOLDER_SECRETS = frozenset(
    {
        "your-super-secret-api-key-change-this",
        "change-me-to-a-long-random-string",
    }
)
MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # App
    APP_NAME: str = "AI Developer Assistant"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_KEY: str = Field(min_length=1)
    FRONTEND_URL: str = "http://localhost:5173"

    # LLM providers
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GROQ_MODEL_NAME: str = "openai/gpt-oss-120b"
    # Groq rate limits are per model, so routing on a small model leaves the
    # answering model's token budget for answers. Empty uses GROQ_MODEL_NAME.
    ROUTER_MODEL_NAME: str = "openai/gpt-oss-20b"
    # Retries after a rate limit wait as long as Groq asks (often 20s+).
    GROQ_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    MOCK_MODE: bool = True
    REQUEST_TIMEOUT: int = Field(default=30, gt=0)

    # Agent
    AGENT_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=2.0)
    AGENT_MAX_TOKENS: int = Field(default=1024, gt=0, le=32_768)
    AGENT_MAX_ITERATIONS: int = Field(default=5, ge=1, le=20)
    AGENT_HISTORY_LIMIT: int = Field(default=4, ge=0, le=100)
    TOOL_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    # Older search results beyond this many characters are sent to the LLM
    # as references only (the latest tool step is always sent in full).
    AGENT_TOOL_CONTEXT_CHARS: int = Field(default=4000, ge=0)
    AGENT_PARALLEL_TOOL_CALLS: bool = True
    AGENT_ROUTING_ENABLED: bool = True
    SUPERVISOR_MAX_ROUNDS: int = Field(default=4, ge=1, le=10)
    # Checkpoints of paused or finished runs expire after this many seconds.
    AGENT_CHECKPOINT_TTL_SECONDS: int = Field(default=7 * 24 * 3600, gt=0)

    # Web search (Tavily); the web_search tool reports an error when unset.
    TAVILY_API_KEY: str | None = None
    WEB_SEARCH_MAX_RESULTS: int = Field(default=3, ge=1, le=10)
    WEB_SEARCH_CACHE_TTL_SECONDS: int = Field(default=600, ge=0)
    WEB_SEARCH_MAX_CALLS_PER_TURN: int = Field(default=2, ge=1, le=10)

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "ai_developer_assistant"

    # JWT
    JWT_SECRET_KEY: str = Field(min_length=1)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, gt=0)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, gt=0)

    # RAG retrieval
    RAG_DISTANCE_THRESHOLD: float = Field(default=0.35, ge=0.0)
    RAG_RETRIEVAL_TOP_K: int = Field(default=10, ge=1)
    RAG_FINAL_TOP_K: int = Field(default=3, ge=1)

    # RAG ingestion
    RAG_MAX_UPLOAD_BYTES: int = Field(default=5 * 1024 * 1024, gt=0)
    RAG_CHUNK_SIZE: int = Field(default=800, ge=100, le=8000)
    RAG_CHUNK_OVERLAP: int = Field(default=100, ge=0)

    # Hybrid search
    RAG_HYBRID_SEARCH: bool = True
    RAG_KEYWORD_TOP_K: int = Field(default=10, ge=1)
    RAG_RRF_K: int = Field(default=60, ge=1)

    # Embeddings; each model gets its own vector collection.
    EMBEDDING_MODEL_NAME: str = Field(default="gemini-embedding-001", min_length=1)

    # Request limits
    MAX_REQUEST_BYTES: int = Field(default=6 * 1024 * 1024, gt=0)
    CHAT_MAX_MESSAGE_CHARS: int = Field(default=8000, ge=1, le=100_000)
    RAG_MAX_TEXT_CHARS: int = Field(default=1_000_000, ge=1)

    # Rate limits (limits syntax, e.g. "10/minute"); per user when the
    # request has a valid access token, otherwise per client IP.
    RATE_LIMIT_ENABLED: bool = True
    # memory:// is per process; use e.g. redis://host:6379 with several workers.
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    RATE_LIMIT_CHAT: str = "5/minute"
    RATE_LIMIT_AGENT: str = "10/minute"
    RATE_LIMIT_RAG: str = "30/minute"
    # Always per IP: login and register have no user yet.
    RATE_LIMIT_AUTH: str = "5/minute"

    # Privacy
    CHAT_HISTORY_RETENTION_DAYS: int = Field(default=90, ge=1, le=3650)
    LOG_REDACT_TOOL_ARGS: bool = True

    @model_validator(mode="after")
    def _check_chunk_overlap(self) -> "Settings":
        if self.RAG_CHUNK_OVERLAP >= self.RAG_CHUNK_SIZE:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
        return self

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        """Refuse to start in production with example or weak secrets."""
        if self.APP_ENV.strip().lower() != "production":
            return self

        problems = []

        if (
            self.JWT_SECRET_KEY in PLACEHOLDER_SECRETS
            or len(self.JWT_SECRET_KEY) < MIN_PRODUCTION_SECRET_LENGTH
        ):
            problems.append(
                "JWT_SECRET_KEY must be a random value of at least "
                f"{MIN_PRODUCTION_SECRET_LENGTH} characters"
            )

        if (
            self.API_KEY in PLACEHOLDER_SECRETS
            or len(self.API_KEY) < MIN_PRODUCTION_SECRET_LENGTH
        ):
            problems.append(
                "API_KEY must be a random value of at least "
                f"{MIN_PRODUCTION_SECRET_LENGTH} characters"
            )

        if self.DEBUG:
            problems.append("DEBUG must be false")

        if problems:
            raise ValueError(
                "Unsafe production configuration: " + "; ".join(problems)
            )

        return self

    # Reranker
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    RERANKER_DEVICE: Literal["auto", "cpu", "cuda"] = "auto"
    RERANKER_SCORE_THRESHOLD: float = 0.0


settings = Settings()

APP_NAME = settings.APP_NAME
APP_ENV = settings.APP_ENV
DEBUG = settings.DEBUG
API_KEY = settings.API_KEY
FRONTEND_URL = settings.FRONTEND_URL

GEMINI_API_KEY = settings.GEMINI_API_KEY
GROQ_API_KEY = settings.GROQ_API_KEY
GROQ_MODEL_NAME = settings.GROQ_MODEL_NAME
ROUTER_MODEL_NAME = settings.ROUTER_MODEL_NAME.strip() or GROQ_MODEL_NAME
GROQ_MAX_RETRIES = settings.GROQ_MAX_RETRIES
MOCK_MODE = settings.MOCK_MODE
REQUEST_TIMEOUT = settings.REQUEST_TIMEOUT

AGENT_TEMPERATURE = settings.AGENT_TEMPERATURE
AGENT_MAX_TOKENS = settings.AGENT_MAX_TOKENS
AGENT_MAX_ITERATIONS = settings.AGENT_MAX_ITERATIONS
AGENT_HISTORY_LIMIT = settings.AGENT_HISTORY_LIMIT
TOOL_TIMEOUT_SECONDS = settings.TOOL_TIMEOUT_SECONDS
AGENT_TOOL_CONTEXT_CHARS = settings.AGENT_TOOL_CONTEXT_CHARS
AGENT_PARALLEL_TOOL_CALLS = settings.AGENT_PARALLEL_TOOL_CALLS
AGENT_ROUTING_ENABLED = settings.AGENT_ROUTING_ENABLED
SUPERVISOR_MAX_ROUNDS = settings.SUPERVISOR_MAX_ROUNDS
AGENT_CHECKPOINT_TTL_SECONDS = settings.AGENT_CHECKPOINT_TTL_SECONDS

TAVILY_API_KEY = settings.TAVILY_API_KEY
WEB_SEARCH_MAX_RESULTS = settings.WEB_SEARCH_MAX_RESULTS
WEB_SEARCH_CACHE_TTL_SECONDS = settings.WEB_SEARCH_CACHE_TTL_SECONDS
WEB_SEARCH_MAX_CALLS_PER_TURN = settings.WEB_SEARCH_MAX_CALLS_PER_TURN

MONGODB_URI = settings.MONGODB_URI
MONGODB_DATABASE = settings.MONGODB_DATABASE

JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

RAG_DISTANCE_THRESHOLD = settings.RAG_DISTANCE_THRESHOLD
RAG_RETRIEVAL_TOP_K = settings.RAG_RETRIEVAL_TOP_K
RAG_FINAL_TOP_K = settings.RAG_FINAL_TOP_K

RAG_MAX_UPLOAD_BYTES = settings.RAG_MAX_UPLOAD_BYTES
RAG_CHUNK_SIZE = settings.RAG_CHUNK_SIZE
RAG_CHUNK_OVERLAP = settings.RAG_CHUNK_OVERLAP

RAG_HYBRID_SEARCH = settings.RAG_HYBRID_SEARCH
RAG_KEYWORD_TOP_K = settings.RAG_KEYWORD_TOP_K
RAG_RRF_K = settings.RAG_RRF_K

EMBEDDING_MODEL_NAME = settings.EMBEDDING_MODEL_NAME

RERANKER_MODEL_NAME = settings.RERANKER_MODEL_NAME
RERANKER_DEVICE = settings.RERANKER_DEVICE
RERANKER_SCORE_THRESHOLD = settings.RERANKER_SCORE_THRESHOLD

MAX_REQUEST_BYTES = settings.MAX_REQUEST_BYTES
CHAT_MAX_MESSAGE_CHARS = settings.CHAT_MAX_MESSAGE_CHARS
RAG_MAX_TEXT_CHARS = settings.RAG_MAX_TEXT_CHARS

RATE_LIMIT_ENABLED = settings.RATE_LIMIT_ENABLED
RATE_LIMIT_STORAGE_URI = settings.RATE_LIMIT_STORAGE_URI
RATE_LIMIT_CHAT = settings.RATE_LIMIT_CHAT
RATE_LIMIT_AGENT = settings.RATE_LIMIT_AGENT
RATE_LIMIT_RAG = settings.RATE_LIMIT_RAG
RATE_LIMIT_AUTH = settings.RATE_LIMIT_AUTH

CHAT_HISTORY_RETENTION_DAYS = settings.CHAT_HISTORY_RETENTION_DAYS
LOG_REDACT_TOOL_ARGS = settings.LOG_REDACT_TOOL_ARGS
