from app.tools.calculator import calculator
from app.services.llm_service import create_chat_model


def create_tool_llm(
    temperature: float,
    max_tokens: int,
):
    llm = create_chat_model(temperature, max_tokens)

    llm_with_tools = llm.bind_tools(
        [calculator],
    )
    return llm_with_tools
