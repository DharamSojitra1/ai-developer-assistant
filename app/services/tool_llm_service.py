from collections.abc import Sequence

from langchain_core.tools import BaseTool

from app.tools.calculator import calculator
from app.services.llm_service import create_chat_model


def create_tool_llm(
    temperature: float,
    max_tokens: int,
    tools: Sequence[BaseTool] = (calculator,),
    **bind_kwargs,
):
    """Chat model bound to `tools`; with no tools, the plain chat model."""
    llm = create_chat_model(temperature, max_tokens)

    if not tools:
        return llm

    return llm.bind_tools(list(tools), **bind_kwargs)
