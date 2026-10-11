from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.database import get_token_usage
from app.dependencies import get_current_user

router = APIRouter(prefix="/usage", tags=["Usage"])

USAGE_FIELDS = ("requests", "llm_calls", "input_tokens", "output_tokens", "total_tokens")


class UsageTotals(BaseModel):
    requests: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class DailyUsage(UsageTotals):
    date: str


class UsageResponse(BaseModel):
    days: int
    totals: UsageTotals
    daily: list[DailyUsage]


@router.get(
    "/me",
    response_model=UsageResponse,
    summary="Your LLM token usage",
    description=(
        "Token usage of the current user's requests, per UTC day, "
        "for the last `days` days (today included)."
    ),
)
async def my_usage(
    current_user: dict = Depends(get_current_user),
    days: int = Query(default=30, ge=1, le=365),
):
    daily = await get_token_usage(current_user["user_id"], days=days)

    totals = {
        name: sum(day.get(name, 0) for day in daily)
        for name in USAGE_FIELDS
    }

    return {"days": days, "totals": totals, "daily": daily}
