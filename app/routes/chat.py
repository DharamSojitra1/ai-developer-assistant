from langchain_core.runnables import history
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.schemas import ChatRequest,ChatResponse
from app.services.chat_service import generate_response
import logging
import time
from app.limiter import limiter
from app.auth import verify_api_key
from app.database import save_chat_history, get_chat_history
from app.config import MODEL_NAME

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Generate AI response",
    description=(
        "Send a message to the AI assistant and receive "
        "a generated response. Requires a valid API key."
    ),
    tags=["Chat"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def chat(request: Request, body:ChatRequest):
    try:
        request_id = request.state.request_id
        logger.info(
            "Chat request started",
            extra={
                "request_id": request.state.request_id,
            },
        )
        start_time = time.perf_counter()

        result = await generate_response(body.message, body.temperature, body.max_tokens)

        duration = time.perf_counter() - start_time

        logger.info(
            "Chat request completed in %.2f seconds",
            duration
        )

        await save_chat_history(
            message=body.message,
            response=result,
            model=MODEL_NAME,
        )

        return ChatResponse(response= result)
    
    except TimeoutError:
        logger.exception(
            "Chat request failed",
            extra={
                "request_id": request.state.request_id,
            },
        )
        raise HTTPException(
            status_code=504,
            detail="AI Provider Request Timed Out"
        )
    except Exception:
        logger.exception(
            "Chat request failed",
            extra={
                "request_id": request.state.request_id,
            },
        )
        raise HTTPException(
            status_code=502,
            detail="AI service is temporarily unavailable"
        )

@router.get("/history")
async def chat_history(
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0)
):
    history = await get_chat_history(
        limit = limit,
        skip= skip
    )

    return {
        "count": len(history),
        "history": history
    }