"""Load and clean stages of the document ingestion pipeline.

The full pipeline is load -> clean -> chunk -> embed -> store; chunking,
embedding, and storage happen in `RAGService.index_document`.
"""

import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePath
from typing import Literal

from pypdf import PdfReader
from pypdf.errors import PdfReadError

DocumentType = Literal["text", "markdown", "pdf"]

DOCUMENT_TYPES: tuple[DocumentType, ...] = ("text", "markdown", "pdf")

EXTENSION_TYPES: dict[str, DocumentType] = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
}

MAX_SOURCE_LENGTH = 255

# Control characters, zero-width/format characters, and unusual whitespace;
# tab, newline, and space are kept.
_CONTROL_CHARS = re.compile(r"[^\S\t\n ]|[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u2028\u2029\ufeff]")
_HORIZONTAL_SPACE = re.compile(r"[ \t]+")
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")
_PDF_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


class DocumentLoadError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedDocument:
    text: str
    source: str
    doc_type: DocumentType


def document_type_for(filename: str) -> DocumentType:
    extension = PurePath(filename).suffix.lower()

    try:
        return EXTENSION_TYPES[extension]
    except KeyError:
        supported = ", ".join(sorted(EXTENSION_TYPES))
        raise DocumentLoadError(
            f"Unsupported file type. Supported types: {supported}"
        ) from None


def normalize_source(source: str) -> str:
    # Keep only the file name; client-supplied paths are not meaningful here.
    name = PurePath(source.replace("\\", "/")).name.strip()

    if not name:
        raise DocumentLoadError("Document source cannot be empty")

    return name[:MAX_SOURCE_LENGTH]


def load_document(filename: str, data: bytes) -> LoadedDocument:
    """Extract raw text from an uploaded file. Blocking for PDFs."""
    doc_type = document_type_for(filename)
    source = normalize_source(filename)

    if not data:
        raise DocumentLoadError("Uploaded file is empty")

    if doc_type == "pdf":
        text = _load_pdf(data)
    else:
        text = _decode_text(data)

    return LoadedDocument(text=text, source=source, doc_type=doc_type)


def clean_text(text: str, doc_type: DocumentType = "text") -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub(" ", text)

    if doc_type == "pdf":
        # PDF text extraction keeps words hyphenated across line breaks.
        text = _PDF_HYPHEN_BREAK.sub(r"\1\2", text)

    lines = [
        _HORIZONTAL_SPACE.sub(" ", line).strip()
        for line in text.split("\n")
    ]

    return _EXTRA_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DocumentLoadError("Text files must be UTF-8 encoded") from None


def _load_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))

        if reader.is_encrypted:
            raise DocumentLoadError("Encrypted PDFs are not supported")

        pages = [page.extract_text() or "" for page in reader.pages]
    except DocumentLoadError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise DocumentLoadError("Could not read PDF file") from exc

    return "\n\n".join(pages)
