from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from app.schemas import ChatRequest,ChatResponse, ChatHistoryResponse
from app.services.chat_service import generate_response, generate_streaming_response
import logging
import time
from app.limiter import limiter
from app.dependencies import get_current_user
from app.database import save_chat_history, get_chat_history
from app.config import GROQ_MODEL_NAME

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Generate AI response",
    description="Generate an AI response. Requires a valid access token.",
    tags=["Chat"],
)
@limiter.limit("5/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        request_id = request.state.request_id

        logger.info(
            "Chat request started",
            extra={"request_id": request_id},
        )

        start_time = time.perf_counter()

        result = await generate_response(
            body.message,
            body.temperature,
            body.max_tokens,
            user_id=current_user["user_id"],
        )

        answer = result["response"]
        sources = result["sources"]

        duration = time.perf_counter() - start_time

        logger.info("Chat request completed in %.2f seconds", duration)

        await save_chat_history(
            user_id=current_user["user_id"],
            message=body.message,
            response=answer,
            model=GROQ_MODEL_NAME,
        )

        return ChatResponse(response=answer, sources=sources)

    except TimeoutError:
        logger.exception(
            "Chat request failed",
            extra={"request_id": request.state.request_id},
        )
        raise HTTPException(
            status_code=504,
            detail="AI Provider Request Timed Out",
        )

    except Exception:
        logger.exception(
            "Chat request failed",
            extra={"request_id": request.state.request_id},
        )
        raise HTTPException(
            status_code=502,
            detail="AI service is temporarily unavailable",
        )

@router.post(
    "/chat/stream",
    summary="Stream AI response",
    description="Stream an AI response token by token. Requires a valid access token.",
    tags=["Chat"],
)
@limiter.limit("5/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    full_response = []

    async def generate():
        async for chunk in generate_streaming_response(
            message=body.message,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            user_id=current_user["user_id"],
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


@router.get(
    "/history",
    response_model=ChatHistoryResponse,
    tags=["Chat"],
)
async def chat_history(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
):
    history = await get_chat_history(
        user_id=current_user["user_id"],
        limit=limit,
        skip=skip,
    )

    return {
        "count": len(history),
        "history": history,
    }