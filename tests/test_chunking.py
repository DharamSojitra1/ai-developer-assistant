import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services.document_service import (
    chunk_document,
    chunking_signature,
    split_document,
)

GUIDE = """# Deployment Guide

Intro paragraph about deploying the service.

## Docker

Build the image with the provided Dockerfile.

```bash
docker build -t assistant .

docker run -p 8000:8000 assistant
```

## Kubernetes

### Scaling

Use a HorizontalPodAutoscaler to scale on CPU.
"""


def test_markdown_chunks_follow_sections_and_carry_heading_path():
    chunks = chunk_document(GUIDE, "markdown", chunk_size=500, chunk_overlap=0)

    assert [chunk.section for chunk in chunks] == [
        "Deployment Guide",
        "Deployment Guide > Docker",
        "Deployment Guide > Kubernetes > Scaling",
    ]
    scaling = chunks[-1]
    assert scaling.text == (
        "Deployment Guide > Kubernetes > Scaling\n\n"
        "Use a HorizontalPodAutoscaler to scale on CPU."
    )


def test_markdown_sections_never_share_a_chunk():
    chunks = chunk_document(GUIDE, "markdown", chunk_size=2000, chunk_overlap=0)

    docker = next(chunk for chunk in chunks if chunk.section.endswith("Docker"))
    assert "HorizontalPodAutoscaler" not in docker.text
    assert "docker build" in docker.text and "docker run" in docker.text


def test_markdown_without_headings_has_no_section():
    chunks = chunk_document("Just a paragraph.", "markdown")

    assert [(chunk.text, chunk.section) for chunk in chunks] == [
        ("Just a paragraph.", "")
    ]


def test_long_markdown_sections_are_split_with_the_heading_on_every_chunk():
    body = " ".join(f"Sentence number {i} about scaling." for i in range(60))
    chunks = chunk_document(
        f"# Ops\n\n## Scaling\n\n{body}",
        "markdown",
        chunk_size=300,
        chunk_overlap=50,
    )

    assert len(chunks) > 1
    assert all(chunk.text.startswith("Ops > Scaling\n\n") for chunk in chunks)
    assert all(
        len(chunk.text) <= 300 + len("Ops > Scaling\n\n") for chunk in chunks
    )


def test_text_splits_on_sentence_boundaries():
    text = " ".join(f"This is sentence {i} of the document." for i in range(40))

    chunks = split_document(text, chunk_size=200, chunk_overlap=0)

    assert len(chunks) > 1
    assert all(chunk.endswith(".") for chunk in chunks)
    assert all(len(chunk) <= 200 for chunk in chunks)


def test_text_overlap_repeats_context_between_chunks():
    text = " ".join(f"Sentence {i} here." for i in range(60))

    chunks = split_document(text, chunk_size=200, chunk_overlap=60)

    for previous, current in zip(chunks, chunks[1:]):
        first_sentence = current.split(".")[0]
        assert first_sentence in previous


def test_pdf_and_text_use_paragraph_aware_splitting():
    text = "First paragraph.\n\nSecond paragraph."

    chunks = chunk_document(text, "pdf", chunk_size=100, chunk_overlap=0)

    assert [chunk.text for chunk in chunks] == [text]


def test_chunking_signature_tracks_strategy_and_settings():
    assert chunking_signature("markdown", 800, 100) == "markdown:800:100"
    assert chunking_signature("pdf", 800, 100) == "recursive:800:100"
    assert chunking_signature("text", 500, 50) != chunking_signature("text", 800, 100)


def test_settings_reject_overlap_not_smaller_than_chunk_size():
    with pytest.raises(ValidationError, match="RAG_CHUNK_OVERLAP"):
        Settings(
            API_KEY="key",
            JWT_SECRET_KEY="secret",
            RAG_CHUNK_SIZE=200,
            RAG_CHUNK_OVERLAP=200,
        )
