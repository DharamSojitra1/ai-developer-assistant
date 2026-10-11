import json
import time

import pytest

from app.tools.calculator import calculator


def run(expression: str) -> dict:
    return json.loads(calculator.invoke({"expression": expression}))


def assert_result(expression: str, expected: str):
    payload = run(expression)

    assert payload == {"ok": True, "result": expected, "error": None}


def assert_error(expression: str, expected_error: str):
    payload = run(expression)

    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"] == expected_error


def test_calculator_addition():
    assert_result("10 + 5", "15")


def test_calculator_multiplication():
    assert_result("20 * 4", "80")


def test_calculator_parentheses():
    assert_result("(10 + 5) * 2", "30")


def test_calculator_power():
    assert_result("2 ** 8", "256")


def test_calculator_division_by_zero():
    assert_error("10 / 0", "Cannot divide by zero.")


def test_calculator_rejects_function_calls():
    assert_error(
        "__import__('os').system('whoami')",
        "Invalid mathematical expression.",
    )


def test_calculator_rejects_python_code():
    assert_error(
        "open('test.txt', 'w')",
        "Invalid mathematical expression.",
    )


def test_calculator_rejects_variables():
    assert_error("x + 10", "Invalid mathematical expression.")


@pytest.mark.parametrize(
    "expression",
    [
        "9 ** 9 ** 9",
        "10 ** 10 ** 10",
        "2 ** 100000",
    ],
)
def test_calculator_rejects_huge_exponents(expression):
    assert_error(expression, "Exponent is too large.")


def test_calculator_rejects_huge_result_with_small_exponent():
    assert_error("99999 ** 999", "Result is too large.")


def test_calculator_rejects_huge_result_from_multiplication():
    assert_error("9 ** 1000 * 9 ** 1000", "Result is too large.")


def test_calculator_rejects_deep_nesting():
    assert_error("-" * 100 + "1", "Expression is too deeply nested.")


def test_calculator_allows_large_but_reasonable_power():
    assert_result("2 ** 1000", str(2 ** 1000))


def test_calculator_rejects_huge_computation_quickly():
    start = time.perf_counter()

    run("9 ** 9 ** 9")

    assert time.perf_counter() - start < 0.1


def test_calculator_schema_rejects_long_expression():
    payload = run("1+" * 500 + "1")

    assert payload["ok"] is False
    assert payload["error"].startswith("Invalid tool input: expression:")
    assert "200" in payload["error"]


def test_calculator_schema_rejects_empty_expression():
    payload = run("")

    assert payload["ok"] is False
    assert payload["error"].startswith("Invalid tool input: expression:")


def test_calculator_schema_rejects_missing_expression():
    payload = json.loads(calculator.invoke({}))

    assert payload["ok"] is False
    assert "expression" in payload["error"]


@pytest.mark.parametrize(
    "expression",
    [
        "(1).__class__",
        "().__class__.__bases__[0].__subclasses__()",
        "lambda: 1",
        "[x for x in range(10)]",
        "'a' * 10",
        "f'{1}'",
        "b'1'",
        "(x := 1)",
        "1 < 2",
        "1 << 1000000",
        "1 if 1 else 2",
        "True + 1",
        "None",
        "1\nimport os",
        "1; 2",
        "1\x00",
        "1 +",
        "((1)",
    ],
)
def test_calculator_rejects_malicious_or_malformed_expressions(expression):
    assert_error(expression, "Invalid mathematical expression.")


@pytest.mark.parametrize(
    "expression",
    [
        "1e308 * 10",
        "1e999",
        "-1e308 * 10",
        "1e308 * 10 - 1e308 * 10",
        "10.0 ** 400",
    ],
)
def test_calculator_rejects_float_overflow(expression):
    assert_error(expression, "Result is too large.")


def test_calculator_rejects_complex_result():
    assert_error("(-8) ** 0.5", "Result is not a real number.")


def test_calculator_handles_floats_and_negative_exponents():
    assert_result("2 ** -1", "0.5")
    assert_result("7 % 3", "1")
    assert_result("-(-5)", "5")


@pytest.mark.parametrize(
    "arguments",
    [
        {"expression": 123},
        {"expression": None},
        {"expression": ["1 + 1"]},
        {"expression": "   "},
        {"expression": "1 + 1", "unexpected": "value"},
    ],
)
def test_calculator_schema_rejects_malformed_arguments(arguments):
    payload = json.loads(calculator.invoke(arguments))

    assert payload["ok"] is False
    assert payload["error"].startswith("Invalid tool input:")


def test_calculator_schema_is_exposed_to_llm():
    schema = calculator.args_schema.model_json_schema()

    assert schema["properties"]["expression"]["maxLength"] == 200
    assert schema["properties"]["expression"]["description"]
