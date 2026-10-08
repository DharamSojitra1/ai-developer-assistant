from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents.agent_service import generate_agent_response, stream_agent_response
from app.config import GROQ_MODEL_NAME
from app.dependencies import get_current_user
from app.schemas import ChatRequest, ChatResponse
from app.database import save_chat_history

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):

    try:
        user_id = current_user["user_id"]

        response = await generate_agent_response(
            user_id=user_id,
            message=request.message,
            model=GROQ_MODEL_NAME,
        )

        return ChatResponse(
            response=response["response"],
            sources=response["sources"],
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        # Don't expose internal implementation details to clients.
        raise HTTPException(
            status_code=500,
            detail="Agent failed to process the request.",
        ) from exc

@router.post("/chat/stream")
async def agent_chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    full_response = []

    async def generate():
        async for chunk in stream_agent_response(
            user_id=current_user["user_id"],
            message=body.message,
        ):

            full_response.append(chunk)
            yield chunk

        complete_response = "".join(full_response)

        await save_chat_history(
            user_id=current_user["user_id"],
            message=body.message,
            response=complete_response,
            model=GROQ_MODEL_NAME,
        )

    return StreamingResponse(
        generate(),
        media_type="text/plain",
    )