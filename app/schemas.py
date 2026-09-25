from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    message: str = Field(...,min_length=1,example="hello")
    temperature: float= Field(0.7,ge=0.0,le=1.0,example=0.7)
    max_tokens: int = Field(1024,gt=0,example=1024)

class ChatResponse(BaseModel):
    response: str = Field(...,example="Hello!")