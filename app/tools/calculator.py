from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """
    Calculate a mathematical expression.

    Use this tool when the user asks for arithmetic
    calculations that should be computed accurately.
    """

    try:
        result = eval(
            expression,
            {"__builtins__": {}},
        )
        return str(result)

    except ZeroDivisionError:
        return "Error: Cannot divide by zero."

    except Exception:
        return "Error: Invalid mathematical expression"