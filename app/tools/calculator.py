import ast
import operator

from langchain_core.tools import tool


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value

        raise ValueError("Only numbers are allowed.")

    if isinstance(node, ast.BinOp):
        operation = _ALLOWED_OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Operator is not allowed.")

        left = _evaluate(node.left)
        right = _evaluate(node.right)

        return operation(left, right)

    if isinstance(node, ast.UnaryOp):
        operation = _ALLOWED_OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Operator is not allowed.")

        operand = _evaluate(node.operand)

        return operation(operand)

    raise ValueError("Invalid mathematical expression.")


@tool
def calculator(expression: str) -> str:
    """
    Calculate a mathematical expression safely.

    Use this tool when the user asks for arithmetic
    calculations that should be computed accurately.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _evaluate(tree.body)

        return str(result)

    except ZeroDivisionError:
        return "Error: Cannot divide by zero."

    except (SyntaxError, ValueError, TypeError):
        return "Error: Invalid mathematical expression."

    except Exception:
        return "Error: Calculation failed."