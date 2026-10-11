from dataclasses import dataclass

from langchain_text_splitters import (
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE

# Paragraphs, then lines, then sentence and clause boundaries, then words.
TEXT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]

MARKDOWN_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]

SECTION_SEPARATOR = " > "


@dataclass(frozen=True)
class Chunk:
    text: str
    section: str = ""


def chunking_signature(
    doc_type: str,
    chunk_size: int = RAG_CHUNK_SIZE,
    chunk_overlap: int = RAG_CHUNK_OVERLAP,
) -> str:
    """Identifies how a document was chunked, so a settings change re-chunks it."""
    strategy = "markdown" if doc_type == "markdown" else "recursive"
    return f"{strategy}:{chunk_size}:{chunk_overlap}"


def split_document(
    text: str,
    chunk_size: int = RAG_CHUNK_SIZE,
    chunk_overlap: int = RAG_CHUNK_OVERLAP,
) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=TEXT_SEPARATORS,
        keep_separator="end",
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]


def chunk_document(
    text: str,
    doc_type: str = "text",
    chunk_size: int = RAG_CHUNK_SIZE,
    chunk_overlap: int = RAG_CHUNK_OVERLAP,
) -> list[Chunk]:
    if doc_type == "markdown":
        return _chunk_markdown(text, chunk_size, chunk_overlap)

    return [Chunk(text=chunk) for chunk in split_document(text, chunk_size, chunk_overlap)]


def _chunk_markdown(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    sections = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS,
        strip_headers=True,
    ).split_text(text)

    # Markdown-aware separators avoid cutting through code fences and lists.
    splitter = RecursiveCharacterTextSplitter.from_language(
        Language.MARKDOWN,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = []

    for section in sections:
        heading = SECTION_SEPARATOR.join(
            section.metadata[level]
            for _, level in MARKDOWN_HEADERS
            if section.metadata.get(level)
        )

        for piece in splitter.split_text(section.page_content):
            piece = piece.strip()

            if not piece:
                continue

            # The heading path gives each chunk the context of its section,
            # for both embeddings and keyword search.
            chunks.append(
                Chunk(
                    text=f"{heading}\n\n{piece}" if heading else piece,
                    section=heading,
                )
            )

    return chunks
