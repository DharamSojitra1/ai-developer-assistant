from app.tools.text_analyzer import analyze_text


def test_analyze_text():
    result = analyze_text.invoke(
        {
            "text": "Hello world\nThis is AI"
        }
    )

    assert "Characters: 22" in result
    assert "Words: 5" in result
    assert "Lines: 2" in result