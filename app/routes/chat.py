from fastapi import APIRouter, HTTPException, Request, Depends, Path, Query
from fastapi.responses import StreamingResponse
from pymongo.errors import ConnectionFailure
from app.schemas import (
    CONVERSATION_ID_PATTERN,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    DeleteHistoryResponse,
)
from app.services.chat_service import generate_response, generate_streaming_response
import logging
import time
import uuid
from typing import Annotated
from app.limiter import limiter
from app.dependencies import get_current_user
from app.database import (
    delete_chat_history,
    delete_conversation,
    get_chat_history,
    get_conversation,
    list_conversations,
    save_chat_history,
)
from app.config import GROQ_MODEL_NAME, RATE_LIMIT_CHAT
from app.guards.injection import screen_input

logger = logging.getLogger(__name__)

router = APIRouter()

CONVERSATION_ID_HEADER = "X-Conversation-ID"

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Generate AI response",
    description="Generate an AI response. Requires a valid access token.",
    tags=["Chat"],
)
@limiter.limit(RATE_LIMIT_CHAT)
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
        screen_input(body.message, "chat_message")

        start_time = time.perf_counter()

        result = await generate_response(
            body.message,
            body.temperature,
            body.max_tokens,
            user_id=current_user["user_id"],
            conversation_id=body.conversation_id,
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
            conversation_id=body.conversation_id or str(uuid.uuid4()),
        )

        return ChatResponse(response=answer, sources=sources)

    except ConnectionFailure:
        # Let the app-level handler answer 503 instead of "AI service" 502.
        raise

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
@limiter.limit(RATE_LIMIT_CHAT)
async def chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    full_response = []
    screen_input(body.message, "chat_message")
    conversation_id = body.conversation_id or str(uuid.uuid4())

    async def generate():
        async for chunk in generate_streaming_response(
            message=body.message,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            user_id=current_user["user_id"],
            conversation_id=body.conversation_id,
        ):
            full_response.append(chunk)
            yield chunk
        
        complete_response = "".join(full_response)

        await save_chat_history(
            user_id=current_user["user_id"],
            message=body.message,
            response=complete_response,
            model=GROQ_MODEL_NAME,
            conversation_id=conversation_id,
        )

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={CONVERSATION_ID_HEADER: conversation_id},
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


@router.delete(
    "/history",
    response_model=DeleteHistoryResponse,
    summary="Delete my chat history",
    description=(
        "Permanently delete all of the caller's chat history. History is "
        "also deleted automatically after the retention period."
    ),
    tags=["Chat"],
)
async def delete_history(
    current_user: dict = Depends(get_current_user),
):
    deleted = await delete_chat_history(current_user["user_id"])

    logger.info("Chat history deleted", extra={"deleted": deleted})

    return {"deleted": deleted}


ConversationId = Annotated[
    str,
    Path(
        pattern=CONVERSATION_ID_PATTERN,
        description="ID of one of the caller's conversations.",
    ),
]


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List my conversations",
    description=(
        "The caller's conversations, most recently active first. The title "
        "is the conversation's first message."
    ),
    tags=["Chat"],
)
async def conversations(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
):
    items = await list_conversations(
        user_id=current_user["user_id"],
        limit=limit,
        skip=skip,
    )

    return {"count": len(items), "conversations": items}


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get a conversation",
    description="Every message of one of the caller's conversations, oldest first.",
    tags=["Chat"],
)
async def conversation(
    conversation_id: ConversationId,
    current_user: dict = Depends(get_current_user),
):
    messages = await get_conversation(
        user_id=current_user["user_id"],
        conversation_id=conversation_id,
    )

    # Another user's conversation is reported as missing, so IDs cannot
    # be probed.
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {"id": conversation_id, "messages": messages}


@router.delete(
    "/conversations/{conversation_id}",
    response_model=DeleteHistoryResponse,
    summary="Delete a conversation",
    description="Permanently delete every message of one of the caller's conversations.",
    tags=["Chat"],
)
async def remove_conversation(
    conversation_id: ConversationId,
    current_user: dict = Depends(get_current_user),
):
    deleted = await delete_conversation(
        user_id=current_user["user_id"],
        conversation_id=conversation_id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    logger.info("Conversation deleted", extra={"deleted": deleted})

    return {"deleted": deleted}