from fastapi import APIRouter, HTTPException
from app.schemas import ChatRequest,ChatResponse
from app.services.chat_service import generate_response

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request:ChatRequest):

    result = generate_response(request.message)

    return {"response" : result}