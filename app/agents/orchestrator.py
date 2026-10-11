"""Top-level agent graph: classify the message, then hand it to one agent.

    classify -> rag_agent | calc_agent | plain_llm | tool_agent | supervisor

Every agent only gets the tools the user's role allows. The route agents
are compiled subgraphs sharing `AgentState`, so a pause for approval inside
one is checkpointed with the run and resumed in place.
"""

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents import calculator_agent, router
from app.agents.prompts import with_security_rules
from app.agents.calculator_agent import (
    SYSTEM_PROMPT,
    AgentState,
    build_tool_agent,
)
from app.agents.supervisor import create_supervisor_graph
from app.config import (
    AGENT_MAX_TOKENS,
    AGENT_ROUTING_ENABLED,
    AGENT_TEMPERATURE,
)
from app.tools.registry import ROLE_USER, get_tools_for_role
from app.utils.agent_logger import logger

RAG_PROMPT = with_security_rules(
    "You answer questions about the application's knowledge base. Always "
    "call search_knowledge_base first and answer only from its results: do "
    "not add facts, examples, or details that the results do not contain, "
    "even if you know them. If the results are empty or do not answer the "
    "question, say the knowledge base does not have enough information to "
    "answer it. When the question has several independent parts, search "
    "for them in the same step so the searches run in parallel."
)

CALC_PROMPT = with_security_rules(
    "You do calculations and text analysis. Always use the calculator tool "
    "for any arithmetic, even if you know the answer, and analyze_text for "
    "text statistics. When several independent calculations are needed, "
    "request all of them in the same step so they run in parallel."
)

CHAT_PROMPT = with_security_rules(
    "You are a helpful AI developer assistant. Answer conversationally and "
    "concisely. You have no tools or document access in this conversation; "
    "if a request needs them, say so instead of guessing."
)

ROUTE_NODES = {
    "knowledge_base": "rag_agent",
    "calculation": "calc_agent",
    "chat": "plain_llm",
    "multi_agent": "supervisor",
    "general": "tool_agent",
}


async def classify(state: AgentState):
    if not AGENT_ROUTING_ENABLED:
        return {"route": router.FALLBACK_ROUTE}

    decision = await router.classify_message(state["messages"])

    logger.info(
        "Agent route selected",
        extra={
            "run_id": state.get("run_id"),
            "route": decision.route,
            "route_reason": decision.reason,
        },
    )

    return {"route": decision.route}


def route_to_agent(state: AgentState) -> str:
    return ROUTE_NODES.get(state.get("route"), ROUTE_NODES["general"])


def create_orchestrator_graph(
    role: str = ROLE_USER,
    temperature: float = AGENT_TEMPERATURE,
    max_tokens: int = AGENT_MAX_TOKENS,
    checkpointer=None,
):
    allowed = {tool.name: tool for tool in get_tools_for_role(role)}

    def tools(*names: str) -> list:
        return [allowed[name] for name in names if name in allowed]

    def agent(agent_tools: list, prompt: str):
        return build_tool_agent(
            agent_tools,
            system_prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    plain = calculator_agent.create_agent_llm(
        [],
        temperature=temperature,
        max_tokens=max_tokens,
        final_answer=True,
    )

    async def plain_llm(state: AgentState):
        response = await plain.ainvoke(
            [SystemMessage(content=CHAT_PROMPT), *state["messages"]]
        )

        return {
            "messages": [response],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "stop_reason": "final_answer",
        }

    builder = StateGraph(AgentState)

    builder.add_node("classify", classify)
    builder.add_node(
        "rag_agent",
        agent(tools("search_knowledge_base"), RAG_PROMPT),
    )
    builder.add_node(
        "calc_agent",
        agent(tools("calculator", "analyze_text"), CALC_PROMPT),
    )
    builder.add_node("plain_llm", plain_llm)
    builder.add_node(
        "tool_agent",
        agent(list(allowed.values()), SYSTEM_PROMPT),
    )
    builder.add_node(
        "supervisor",
        create_supervisor_graph(
            role=role,
            temperature=temperature,
            max_tokens=max_tokens,
        ),
    )

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_to_agent,
        {node: node for node in ROUTE_NODES.values()},
    )

    for node in ROUTE_NODES.values():
        builder.add_edge(node, END)

    return builder.compile(checkpointer=checkpointer)
