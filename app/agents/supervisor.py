"""Multi-agent supervisor: delegates steps to specialised workers.

The supervisor repeatedly picks a worker (research, analysis, coding) and a
task, runs it in the worker's own message list, and records the result as a
finding. When it decides to finish, or after `SUPERVISOR_MAX_ROUNDS`
hand-offs, one final LLM call writes the answer from the findings.
"""

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agents import calculator_agent
from app.agents.calculator_agent import AgentState, build_tool_agent
from app.agents.prompts import with_security_rules
from app.config import AGENT_MAX_TOKENS, AGENT_TEMPERATURE, SUPERVISOR_MAX_ROUNDS
from app.services.llm_service import create_chat_model
from app.tools.registry import ROLE_USER, get_tools_for_role
from app.utils.agent_logger import logger

FINISH = "finish"
WorkerName = Literal["research", "analysis", "coding"]

WORKERS: dict[str, dict] = {
    "research": {
        "tools": ("search_knowledge_base",),
        "prompt": with_security_rules(
            "You are a research worker. Look up the task in the knowledge "
            "base with search_knowledge_base and report only what the "
            "results say, citing the documents. If they do not cover it, "
            "say so."
        ),
    },
    "analysis": {
        "tools": ("calculator", "analyze_text"),
        "prompt": with_security_rules(
            "You are an analysis worker. Use the calculator for every "
            "computation and analyze_text for text statistics. Report the "
            "results briefly with the numbers you computed."
        ),
    },
    "coding": {
        "tools": (),
        "prompt": with_security_rules(
            "You are a coding worker. Write correct, idiomatic, minimal code "
            "for the task with a one-line explanation. Use the findings you "
            "are given; do not invent APIs that are not in them."
        ),
    },
}

SUPERVISOR_PROMPT = with_security_rules(
    "You coordinate workers to answer the user's request.\n"
    "- research: looks things up in the knowledge base.\n"
    "- analysis: does calculations and text statistics.\n"
    "- coding: writes code.\n"
    "Pick the next worker and give it one concrete, self-contained task, "
    "or pick finish once the findings are enough to answer. Do not repeat "
    "a task that already has a finding."
)

FINALIZE_PROMPT = with_security_rules(
    "Write the final answer to the user's request using only the workers' "
    "findings below. Be concise. If the findings are incomplete, say what "
    "is missing instead of guessing."
)

SUPERVISOR_TAGS = ["nostream", "agent:supervisor"]


class SupervisorDecision(BaseModel):
    next: WorkerName | Literal["finish"] = Field(
        description="The worker to run next, or finish.",
    )
    task: str = Field(
        default="",
        max_length=1000,
        description="The worker's task; empty when finishing.",
    )


def format_findings(findings: list[dict]) -> str:
    if not findings:
        return "No findings yet."

    return "\n\n".join(
        f"[{index}] {finding['worker']} - task: {finding['task']}\n"
        f"{finding['result']}"
        for index, finding in enumerate(findings, start=1)
    )


def _request_and_findings(state: AgentState) -> str:
    return (
        f"User request:\n{state.get('user_message', '')}\n\n"
        f"Findings so far:\n{format_findings(state.get('findings') or [])}"
    )


async def decide_next(state: AgentState) -> SupervisorDecision:
    """Ask the supervisor model for the next step; finish on any failure."""
    try:
        model = (
            create_chat_model(temperature=0, max_tokens=300)
            .with_structured_output(SupervisorDecision)
            .with_config(tags=SUPERVISOR_TAGS, run_name="supervisor_decision")
        )

        decision = await model.ainvoke(
            [
                SystemMessage(content=SUPERVISOR_PROMPT),
                HumanMessage(content=_request_and_findings(state)),
            ]
        )

        if isinstance(decision, dict):
            decision = SupervisorDecision.model_validate(decision)

        return decision
    except Exception as exc:
        logger.warning(
            "Supervisor decision failed; finishing with current findings",
            extra={"error_type": type(exc).__name__},
        )
        return SupervisorDecision(next=FINISH)


def _merge_sources(existing: list[dict], new: list[dict]) -> list[dict]:
    merged = list(existing)
    seen = {(s.get("document_id"), s.get("text")) for s in merged}

    for source in new:
        key = (source.get("document_id"), source.get("text"))

        if key not in seen:
            seen.add(key)
            merged.append(source)

    return merged


def create_supervisor_graph(
    role: str = ROLE_USER,
    temperature: float = AGENT_TEMPERATURE,
    max_tokens: int = AGENT_MAX_TOKENS,
    max_rounds: int = SUPERVISOR_MAX_ROUNDS,
):
    allowed = {tool.name: tool for tool in get_tools_for_role(role)}

    workers = {
        name: build_tool_agent(
            [allowed[tool] for tool in spec["tools"] if tool in allowed],
            system_prompt=spec["prompt"],
            temperature=temperature,
            max_tokens=max_tokens,
            final_answer=False,
        )
        for name, spec in WORKERS.items()
    }

    async def supervise(state: AgentState):
        rounds = state.get("supervisor_rounds", 0)

        if rounds >= max_rounds:
            logger.info(
                "Supervisor reached the maximum rounds",
                extra={"supervisor_rounds": rounds},
            )
            return {
                "next_worker": FINISH,
                "worker_task": "",
                "stop_reason": "supervisor_max_rounds",
            }

        decision = await decide_next(state)
        task = decision.task.strip()

        if decision.next != FINISH and not task:
            task = state.get("user_message", "")

        return {"next_worker": decision.next, "worker_task": task}

    async def run_worker(state: AgentState):
        name = state["next_worker"]
        task = state["worker_task"]
        findings = list(state.get("findings") or [])

        prompt = task

        if findings:
            prompt += f"\n\nFindings from other workers:\n{format_findings(findings)}"

        result = await workers[name].ainvoke(
            {
                "messages": [HumanMessage(content=prompt)],
                "iteration_count": 0,
                "sources": [],
                "tool_calls": [],
            }
        )

        findings.append(
            {
                "worker": name,
                "task": task,
                "result": result["messages"][-1].content,
            }
        )

        return {
            "findings": findings,
            "supervisor_rounds": state.get("supervisor_rounds", 0) + 1,
            "sources": _merge_sources(
                state.get("sources") or [],
                result.get("sources") or [],
            ),
            "tool_calls": [
                *(state.get("tool_calls") or []),
                *(result.get("tool_calls") or []),
            ],
            "iteration_count": (
                state.get("iteration_count", 0)
                + result.get("iteration_count", 0)
            ),
        }

    llm = calculator_agent.create_agent_llm(
        [],
        temperature=temperature,
        max_tokens=max_tokens,
        final_answer=True,
    )

    async def finalize(state: AgentState):
        response = await llm.ainvoke(
            [
                SystemMessage(content=FINALIZE_PROMPT),
                HumanMessage(content=_request_and_findings(state)),
            ]
        )

        return {
            "messages": [AIMessage(content=response.content)],
            "stop_reason": state.get("stop_reason") or "final_answer",
        }

    def next_step(state: AgentState):
        return "finalize" if state["next_worker"] == FINISH else "run_worker"

    builder = StateGraph(AgentState)

    builder.add_node("supervise", supervise)
    builder.add_node("run_worker", run_worker)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "supervise")
    builder.add_conditional_edges(
        "supervise",
        next_step,
        {"run_worker": "run_worker", "finalize": "finalize"},
    )
    builder.add_edge("run_worker", "supervise")
    builder.add_edge("finalize", END)

    return builder.compile()
