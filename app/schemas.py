from pydantic import EmailStr
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
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
        json_schema_extra={"example": 1024}
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


class ChatResponse(BaseModel):
    response: str = Field(
        ...,
        json_schema_extra={"example": "Hello!"}
    )

class ChatHistoryItem(BaseModel):
    id: str
    message: str
    response: str
    model:str
    created_at: datetime

class ChatHistoryResponse(BaseModel):
    count: int
    history: list[ChatHistoryItem]


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