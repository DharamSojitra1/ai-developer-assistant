import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pymongo.errors import ConnectionFailure

from app.agents.agent_service import (
    STATUS_AWAITING_APPROVAL,
    RunNotFoundError,
    RunNotPendingError,
    generate_agent_response,
    resume_agent_run,
    stream_agent_response,
)
from app.config import GROQ_MODEL_NAME, RATE_LIMIT_AGENT
from app.dependencies import get_current_user
from app.limiter import limiter
from app.schemas import AgentChatResponse, ApprovalDecision, ChatRequest
from app.tools.registry import ROLE_USER
from app.database import save_chat_history

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)

RUN_ID_HEADER = "X-Agent-Run-ID"


@router.post("/chat", response_model=AgentChatResponse)
@limiter.limit(RATE_LIMIT_AGENT)
async def agent_chat(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):

    try:
        user_id = current_user["user_id"]

        response = await generate_agent_response(
            user_id=user_id,
            message=body.message,
            model=GROQ_MODEL_NAME,
            role=current_user.get("role", ROLE_USER),
        )

        return AgentChatResponse(**response)

    except ConnectionFailure:
        # Let the app-level handler answer 503 instead of a generic 500.
        raise

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


@router.post(
    "/runs/{run_id}/approval",
    response_model=AgentChatResponse,
)
@limiter.limit(RATE_LIMIT_AGENT)
async def approve_agent_run(
    request: Request,
    run_id: str,
    decision: ApprovalDecision,
    current_user: dict = Depends(get_current_user),
):
    """Approve or reject the sensitive action a paused run is waiting on."""
    try:
        response = await resume_agent_run(
            user_id=current_user["user_id"],
            run_id=run_id,
            approved=decision.approved,
            model=GROQ_MODEL_NAME,
            role=current_user.get("role", ROLE_USER),
        )

        return AgentChatResponse(**response)

    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc

    except RunNotPendingError as exc:
        raise HTTPException(
            status_code=409,
            detail="This run is not waiting for an approval.",
        ) from exc

    except ConnectionFailure:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Agent failed to process the request.",
        ) from exc


@router.post("/chat/stream")
@limiter.limit(RATE_LIMIT_AGENT)
async def agent_chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    full_response = []
    run_id = str(uuid.uuid4())
    outcome: dict = {}

    async def generate():
        async for chunk in stream_agent_response(
            user_id=current_user["user_id"],
            message=body.message,
            role=current_user.get("role", ROLE_USER),
            run_id=run_id,
            outcome=outcome,
        ):

            full_response.append(chunk)
            yield chunk

        # A run waiting for approval is saved once it completes.
        if outcome.get("status") == STATUS_AWAITING_APPROVAL:
            return

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
        headers={RUN_ID_HEADER: run_id},
    )
