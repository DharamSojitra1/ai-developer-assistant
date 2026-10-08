from langchain_core.tools import tool

@tool
def analyze_text(text: str) -> str:
    """
    Analyze text and return basic information such as
    character count, word count, and line count.
    """

    character_count = len(text)
    word_count = len(text.split())
    line_count = len(text.splitlines())

    return (
        f"Characters: {character_count}\n"
        f"Words: {word_count}\n"
        f"Lines: {line_count}"
    )