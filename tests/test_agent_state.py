from app.agents.calculator_agent import AgentState


def test_agent_state_has_required_fields():
    state: AgentState = {
        "messages": [],
        "iteration_count": 0,
        "sources": [],
    }

    assert state["messages"] == []
    assert state["iteration_count"] == 0
    assert state["sources"] == []