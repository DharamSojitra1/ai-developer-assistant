from pydantic import EmailStr
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Literal

from app.config import CHAT_MAX_MESSAGE_CHARS, RAG_MAX_TEXT_CHARS

MAX_RESPONSE_TOKENS = 4096
MAX_SEARCH_QUERY_CHARS = 500
CONVERSATION_ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=CHAT_MAX_MESSAGE_CHARS,
        json_schema_extra={"example": "hello"}
    )

    temperature: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.7}
    )

    max_tokens: int = Field(
        1024,
        gt=0,
        le=MAX_RESPONSE_TOKENS,
        json_schema_extra={"example": 1024}
    )

    conversation_id: str | None = Field(
        default=None,
        pattern=CONVERSATION_ID_PATTERN,
        description=(
            "Conversation this message belongs to. Context comes only from "
            "earlier messages in it. When omitted, a new conversation is "
            "started and context comes from the user's recent messages."
        ),
        json_schema_extra={"example": "3f2b8c1e-6d4a-4f7e-9a51-0c8e2d7b6a90"},
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Message cannot be Empty or Whitespace"
            )

        return value

class ChatHistoryItem(BaseModel):
    id: str
    message: str
    response: str
    model:str
    created_at: datetime
    conversation_id: str | None = None

class ChatHistoryResponse(BaseModel):
    count: int
    history: list[ChatHistoryItem]


class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    count: int
    conversations: list[ConversationSummary]


class ConversationDetail(BaseModel):
    id: str
    messages: list[ChatHistoryItem]


class DeleteHistoryResponse(BaseModel):
    deleted: int


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: EmailStr

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

DocumentType = Literal["text", "markdown", "pdf"]
Visibility = Literal["shared", "private"]


class IndexDocumentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=RAG_MAX_TEXT_CHARS)
    document_id: str | None = Field(default=None, min_length=1, max_length=128)
    source: str = Field(default="api", min_length=1, max_length=255)
    doc_type: Literal["text", "markdown"] = "text"
    visibility: Visibility = Field(
        default="private",
        description="Shared documents are visible to every user; only admins can add them.",
    )


class IndexDocumentResponse(BaseModel):
    document_id: str
    status: Literal["indexed", "unchanged"] = Field(
        description="`unchanged` when identical content was already indexed under this ID.",
    )
    chunks_indexed: int
    chunks_embedded: int = Field(
        description="Chunks sent to the embedding model; the rest reused stored embeddings.",
    )
    source: str
    doc_type: DocumentType
    visibility: Visibility

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_SEARCH_QUERY_CHARS)
    top_k: int = Field(default=3, ge=1, le=20)
    source: str | None = Field(default=None, min_length=1, max_length=255)
    doc_type: DocumentType | None = None

class SearchResult(BaseModel):
    id: str
    text: str
    distance: float | None = Field(
        description="Vector distance; null for keyword-only matches.",
    )
    keyword_score: float | None = None
    rerank_score: float | None = None
    metadata: dict

class SearchResponse(BaseModel):
    results: list[SearchResult]

class SourceReference(BaseModel):
    document_id: str
    text: str
    # Set for web results; document_id is then the URL.
    url: str | None = None
    title: str | None = None


AgentRoute = Literal[
    "knowledge_base",
    "web",
    "calculation",
    "chat",
    "multi_agent",
    "general",
]

AgentRunStatus = Literal["completed", "awaiting_approval"]


class ApprovalRequest(BaseModel):
    """A sensitive action the agent wants to take, waiting for the user."""

    tool_call_id: str
    action: str
    document_id: str
    source: str | None = None
    found: bool = Field(
        description="Whether the document exists and belongs to the user.",
    )


class ChatResponse(BaseModel):
    response: str = Field(
        ...,
        json_schema_extra={"example": "Hello!"}
    )
    sources: list[SourceReference] = Field(
        default_factory=list
    )


class AgentChatResponse(ChatResponse):
    run_id: str
    conversation_id: str | None = None
    route: AgentRoute | None = None
    status: AgentRunStatus
    approval: list[ApprovalRequest] | None = Field(
        default=None,
        description=(
            "Actions awaiting approval when status is awaiting_approval; "
            "answer them with POST /api/agent/runs/{run_id}/approval."
        ),
    )


class ApprovalDecision(BaseModel):
    approved: bool