from langchain_core.tools import tool
from pydantic import Field

from app.tools.schemas import NonBlankStr, StrictToolInput
from app.tools.tool_result import handle_validation_error, tool_success


MAX_TEXT_LENGTH = 10_000


class TextAnalyzerInput(StrictToolInput):
    text: NonBlankStr = Field(
        ...,
        max_length=MAX_TEXT_LENGTH,
        description="The text to analyze.",
    )


@tool(args_schema=TextAnalyzerInput)
def analyze_text(text: str) -> str:
    """
    Analyze text and return basic information such as
    character count, word count, and line count.
    """

    return tool_success(
        {
            "characters": len(text),
            "words": len(text.split()),
            "lines": len(text.splitlines()),
        }
    )


analyze_text.handle_validation_error = handle_validation_error
