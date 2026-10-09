from app.tools.calculator import calculator


def test_calculator_addition():
    result = calculator.invoke({"expression": "10 + 5"})

    assert result == "15"


def test_calculator_multiplication():
    result = calculator.invoke({"expression": "20 * 4"})

    assert result == "80"


def test_calculator_parentheses():
    result = calculator.invoke({"expression": "(10 + 5) * 2"})

    assert result == "30"


def test_calculator_power():
    result = calculator.invoke({"expression": "2 ** 8"})

    assert result == "256"


def test_calculator_division_by_zero():
    result = calculator.invoke({"expression": "10 / 0"})

    assert result == "Error: Cannot divide by zero."


def test_calculator_rejects_function_calls():
    result = calculator.invoke(
        {"expression": "__import__('os').system('whoami')"}
    )

    assert result == "Error: Invalid mathematical expression."


def test_calculator_rejects_python_code():
    result = calculator.invoke(
        {"expression": "open('test.txt', 'w')"}
    )

    assert result == "Error: Invalid mathematical expression."


def test_calculator_rejects_variables():
    result = calculator.invoke(
        {"expression": "x + 10"}
    )

    assert result == "Error: Invalid mathematical expression."