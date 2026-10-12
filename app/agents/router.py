from typing import get_args

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from app.agents.prompts import with_security_rules
from app.config import ROUTER_MODEL_NAME
from app.schemas import AgentRoute
from app.services.llm_service import create_chat_model
from app.utils.agent_logger import logger

ROUTES: tuple[str, ...] = get_args(AgentRoute)
FALLBACK_ROUTE = "general"

# Classification is an internal step: its output is never streamed.
CLASSIFIER_TAGS = ["nostream", "agent:classifier"]

CLASSIFIER_PROMPT = with_security_rules(
    "Classify the user's latest message for routing. Pick exactly one route:\n"
    "- knowledge_base: questions about the application's documents or "
    "knowledge base (how a feature works, configuration, deployment, "
    "documentation lookups).\n"
    "- web: questions needing current, real-world information that may "
    "have changed recently (latest package versions or releases, news, "
    "recent changes to public libraries or services, current events).\n"
    "- calculation: arithmetic, numeric computations, or analyzing a given "
    "piece of text (word or line counts).\n"
    "- chat: greetings, small talk, or general questions answerable without "
    "tools or documents.\n"
    "- multi_agent: requests that need several distinct steps combining "
    "research in the knowledge base or on the web, calculations, and/or "
    "writing code.\n"
    "- general: anything else, including requests to delete a document, or "
    "when unsure.\n"
    "Use earlier messages only to resolve references in the latest one."
)


class RouteDecision(BaseModel):
    route: AgentRoute = Field(description="Which agent should handle it.")
    reason: str = Field(
        default="",
        max_length=300,
        description="One short sentence explaining the choice.",
    )


def create_classifier():
    return (
        create_chat_model(
            temperature=0,
            max_tokens=200,
            model=ROUTER_MODEL_NAME,
        )
        .with_structured_output(RouteDecision)
        .with_config(tags=CLASSIFIER_TAGS, run_name="route_classifier")
    )


async def classify_message(messages: list) -> RouteDecision:
    """Pick the agent for the conversation's latest message.

    Never raises: any failure (API error, malformed output) falls back to
    the general tool agent, which can handle every request.
    """
    try:
        decision = await create_classifier().ainvoke(
            [SystemMessage(content=CLASSIFIER_PROMPT), *messages]
        )

        if isinstance(decision, dict):
            decision = RouteDecision.model_validate(decision)

        if not isinstance(decision, RouteDecision):
            raise ValueError(f"Unexpected classifier output: {decision!r}")

        return decision
    except Exception as exc:
        logger.warning(
            "Route classification failed; using the general agent",
            extra={
                "error_type": type(exc).__name__,
                "fallback_route": FALLBACK_ROUTE,
            },
        )
        return RouteDecision(
            route=FALLBACK_ROUTE,
            reason="classifier unavailable",
        )
