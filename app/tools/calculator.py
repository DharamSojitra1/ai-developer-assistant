import ast
import math
import operator

from langchain_core.tools import tool
from pydantic import Field

from app.tools.schemas import NonBlankStr, StrictToolInput
from app.tools.tool_result import (
    handle_validation_error,
    tool_error,
    tool_success,
)


MAX_EXPRESSION_LENGTH = 200
MAX_EXPONENT = 1000
# Must stay below Python's int-to-str limit (4300 digits by default).
MAX_RESULT_DIGITS = 1000
MAX_DEPTH = 50

_MAX_RESULT_VALUE = 10 ** MAX_RESULT_DIGITS


class CalculationLimitError(Exception):
    pass


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


def _check_result(value):
    if isinstance(value, complex):
        raise CalculationLimitError("Result is not a real number.")

    # Float overflow yields inf/nan silently instead of raising.
    if isinstance(value, float) and not math.isfinite(value):
        raise CalculationLimitError("Result is too large.")

    if isinstance(value, int) and abs(value) >= _MAX_RESULT_VALUE:
        raise CalculationLimitError("Result is too large.")

    return value


def _safe_pow(base, exponent):
    if abs(exponent) > MAX_EXPONENT:
        raise CalculationLimitError("Exponent is too large.")

    # Estimate the digit count before computing, so a huge base with a
    # small exponent (e.g. 99999 ** 999) is rejected without doing the work.
    if abs(base) > 1:
        estimated_digits = abs(exponent) * math.log10(abs(base))

        if estimated_digits > MAX_RESULT_DIGITS:
            raise CalculationLimitError("Result is too large.")

    return base ** exponent


def _evaluate(node, depth=0):
    if depth > MAX_DEPTH:
        raise CalculationLimitError("Expression is too deeply nested.")

    if isinstance(node, ast.Constant):
        # bool is a subclass of int, so True/False must be rejected explicitly.
        if isinstance(node.value, bool):
            raise ValueError("Only numbers are allowed.")

        if isinstance(node.value, (int, float)):
            return _check_result(node.value)

        raise ValueError("Only numbers are allowed.")

    if isinstance(node, ast.BinOp):
        operation = _ALLOWED_OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Operator is not allowed.")

        left = _evaluate(node.left, depth + 1)
        right = _evaluate(node.right, depth + 1)

        if isinstance(node.op, ast.Pow):
            return _check_result(_safe_pow(left, right))

        return _check_result(operation(left, right))

    if isinstance(node, ast.UnaryOp):
        operation = _ALLOWED_OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Operator is not allowed.")

        operand = _evaluate(node.operand, depth + 1)

        return _check_result(operation(operand))

    raise ValueError("Invalid mathematical expression.")


class CalculatorInput(StrictToolInput):
    expression: NonBlankStr = Field(
        ...,
        max_length=MAX_EXPRESSION_LENGTH,
        description="Arithmetic expression to evaluate, e.g. '(10 + 5) * 2'.",
    )


@tool(args_schema=CalculatorInput)
def calculator(expression: str) -> str:
    """
    Calculate a mathematical expression safely.

    Use this tool when the user asks for arithmetic
    calculations that should be computed accurately.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _evaluate(tree.body)

        return tool_success(str(result))

    except ZeroDivisionError:
        return tool_error("Cannot divide by zero.")

    except CalculationLimitError as exc:
        return tool_error(str(exc))

    except OverflowError:
        return tool_error("Result is too large.")

    except (SyntaxError, ValueError, TypeError):
        return tool_error("Invalid mathematical expression.")

    except Exception:
        return tool_error("Calculation failed.")


calculator.handle_validation_error = handle_validation_error