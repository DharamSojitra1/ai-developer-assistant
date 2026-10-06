from app.services.document_service import split_document


def test_split_document():
    text = "FastAPI is a Python framework. " * 100

    chunks = split_document(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)