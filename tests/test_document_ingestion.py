import io

import pytest
from pypdf import PdfWriter

from app.services.document_service import chunking_signature
from app.services.ingestion_service import (
    DocumentLoadError,
    clean_text,
    load_document,
)
from app.services.rag_service import (
    DocumentPermissionError,
    RAGService,
    Requester,
    build_search_filter,
)
from app.services.vector_store_service import VectorStoreService
from app.utils.hashing import text_hash

ALICE = Requester(user_id="alice")
BOB = Requester(user_id="bob")
ADMIN = Requester(user_id="admin", is_admin=True)


def make_pdf(text: str) -> bytes:
    """A one-page PDF whose text layer contains `text` (ASCII only)."""
    stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = []

    for number, body in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(b"%d 0 obj\n%s\nendobj\n" % (number, body))

    xref_offset = output.tell()
    output.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))

    for offset in offsets:
        output.write(b"%010d 00000 n \n" % offset)

    output.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref_offset)
    )
    return output.getvalue()


# --- Load ---


@pytest.mark.parametrize(
    ("filename", "doc_type"),
    [("notes.txt", "text"), ("README.MD", "markdown"), ("guide.markdown", "markdown")],
)
def test_load_text_files(filename, doc_type):
    document = load_document(filename, "\ufeffHello world".encode("utf-8"))

    assert document.text == "Hello world"
    assert document.doc_type == doc_type
    assert document.source == filename


def test_load_pdf_extracts_text():
    document = load_document("manual.pdf", make_pdf("FastAPI ingestion test"))

    assert document.doc_type == "pdf"
    assert "FastAPI ingestion test" in document.text


def test_load_strips_client_paths_from_source():
    document = load_document("..\\..\\secret/dir/notes.txt", b"text")

    assert document.source == "notes.txt"


@pytest.mark.parametrize(
    ("filename", "data", "message"),
    [
        ("image.png", b"data", "Unsupported file type"),
        ("notes.txt", b"", "Uploaded file is empty"),
        ("notes.txt", "café".encode("latin-1"), "must be UTF-8"),
        ("broken.pdf", b"not a pdf", "Could not read PDF file"),
    ],
)
def test_load_rejects_bad_files(filename, data, message):
    with pytest.raises(DocumentLoadError, match=message):
        load_document(filename, data)


def test_load_rejects_encrypted_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    output = io.BytesIO()
    writer.write(output)

    with pytest.raises(DocumentLoadError, match="Encrypted PDFs"):
        load_document("locked.pdf", output.getvalue())


# --- Clean ---


def test_clean_text_normalizes_whitespace_and_control_characters():
    raw = (
        "  Title\r\n\r\n\r\n\r\nFirst\t\t line\x00 with\u200b"
        " zero-width   chars  \n\n\n\nﬁnal"
    )

    assert clean_text(raw) == (
        "Title\n\nFirst line with zero-width chars\n\nfinal"
    )


def test_clean_text_rejoins_pdf_hyphenation_only_for_pdfs():
    raw = "retrieval aug-\nmented generation"

    assert clean_text(raw, "pdf") == "retrieval augmented generation"
    assert clean_text(raw, "text") == raw


# --- Filters ---


def test_search_filter_without_user_only_matches_shared_documents():
    assert build_search_filter() == {"visibility": "shared"}


def test_search_filter_combines_access_source_and_type():
    where = build_search_filter(
        user_id="alice", source="guide.md", doc_type="markdown"
    )

    access, source, doc_type = where["$and"]
    assert {"visibility": "shared"} in access["$or"]
    assert {
        "$and": [{"visibility": "private"}, {"owner_id": "alice"}]
    } in access["$or"]
    assert source == {"source": "guide.md"}
    assert doc_type == {"doc_type": "markdown"}


# --- Pipeline against a real Chroma collection (`isolated_rag_service`) ---


def document_ids(results: list[dict]) -> set[str]:
    return {result["metadata"]["document_id"] for result in results}


async def seed(service: RAGService) -> None:
    await service.index_document(
        "Shared handbook text.",
        "handbook",
        source="handbook.md",
        doc_type="markdown",
        visibility="shared",
        requester=ADMIN,
    )
    await service.index_document(
        "Alice private notes.",
        "alice-notes",
        source="notes.txt",
        visibility="private",
        requester=ALICE,
    )
    await service.index_document(
        "Bob private notes.",
        "bob-notes",
        source="notes.txt",
        visibility="private",
        requester=BOB,
    )


@pytest.mark.asyncio
async def test_index_stores_cleaned_chunks_with_metadata(isolated_rag_service):
    result = await isolated_rag_service.index_document(
        "  Alice   notes \r\n",
        "alice-notes",
        source="C:\\Users\\alice\\notes.txt",
        visibility="private",
        requester=ALICE,
    )

    assert result == {
        "document_id": "alice-notes",
        "status": "indexed",
        "chunks_indexed": 1,
        "chunks_embedded": 1,
        "source": "notes.txt",
        "doc_type": "text",
        "visibility": "private",
    }

    stored = isolated_rag_service.vector_store.collection.get(
        ids=["alice-notes_0"], include=["documents", "metadatas"]
    )
    assert stored["documents"] == ["Alice notes"]
    assert stored["metadatas"][0] == {
        "document_id": "alice-notes",
        "chunk_index": 0,
        "source": "notes.txt",
        "doc_type": "text",
        "visibility": "private",
        "owner_id": "alice",
        "content_hash": text_hash("Alice notes"),
        "chunk_hash": text_hash("Alice notes"),
        "chunking": chunking_signature("text"),
        "embedding_model": "test-embedding-model",
        "section": "",
    }


@pytest.mark.asyncio
async def test_index_rejects_text_that_cleans_to_nothing(isolated_rag_service):
    with pytest.raises(ValueError, match="no extractable text"):
        await isolated_rag_service.index_document("\x00\u200b\x07")


@pytest.mark.asyncio
async def test_retrieve_scopes_results_to_shared_and_own_documents(
    isolated_rag_service,
):
    await seed(isolated_rag_service)

    alice = await isolated_rag_service.retrieve("notes", user_id="alice")
    bob = await isolated_rag_service.retrieve("notes", user_id="bob")
    anonymous = await isolated_rag_service.retrieve("notes")

    assert document_ids(alice) == {"handbook", "alice-notes"}
    assert document_ids(bob) == {"handbook", "bob-notes"}
    assert document_ids(anonymous) == {"handbook"}


@pytest.mark.asyncio
async def test_admins_do_not_see_other_users_private_documents(
    isolated_rag_service,
):
    await seed(isolated_rag_service)

    results = await isolated_rag_service.retrieve("notes", user_id="admin")

    assert document_ids(results) == {"handbook"}


@pytest.mark.asyncio
async def test_retrieve_filters_by_source_and_document_type(isolated_rag_service):
    await seed(isolated_rag_service)

    by_source = await isolated_rag_service.retrieve(
        "notes", user_id="alice", source="notes.txt"
    )
    by_type = await isolated_rag_service.retrieve(
        "notes", user_id="alice", doc_type="markdown"
    )
    no_match = await isolated_rag_service.retrieve(
        "notes", user_id="alice", doc_type="pdf"
    )

    assert document_ids(by_source) == {"alice-notes"}
    assert document_ids(by_type) == {"handbook"}
    assert no_match == []


@pytest.mark.asyncio
async def test_owner_can_reindex_private_document(isolated_rag_service):
    await seed(isolated_rag_service)

    result = await isolated_rag_service.index_document(
        "Alice updated notes.",
        "alice-notes",
        visibility="private",
        requester=ALICE,
    )

    assert result["chunks_indexed"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("document_id", "visibility", "requester", "message"),
    [
        ("bob-notes", "private", ALICE, "cannot modify"),
        ("bob-notes", "private", ADMIN, "cannot modify"),
        ("handbook", "private", ALICE, "cannot modify"),
        ("new-doc", "shared", ALICE, "Only admins can add shared"),
    ],
)
async def test_index_rejects_writes_the_requester_does_not_own(
    isolated_rag_service, document_id, visibility, requester, message
):
    await seed(isolated_rag_service)

    with pytest.raises(DocumentPermissionError, match=message):
        await isolated_rag_service.index_document(
            "Hijacked text.",
            document_id,
            visibility=visibility,
            requester=requester,
        )

    results = await isolated_rag_service.retrieve("notes", user_id="bob")
    assert "Hijacked text." not in {result["text"] for result in results}


@pytest.mark.asyncio
async def test_delete_permissions(isolated_rag_service):
    await seed(isolated_rag_service)

    with pytest.raises(DocumentPermissionError):
        isolated_rag_service.delete_document("bob-notes", requester=ALICE)

    with pytest.raises(DocumentPermissionError):
        isolated_rag_service.delete_document("handbook", requester=ALICE)

    own = isolated_rag_service.delete_document("alice-notes", requester=ALICE)
    moderated = isolated_rag_service.delete_document("bob-notes", requester=ADMIN)

    assert own["chunks_deleted"] == 1
    assert moderated["chunks_deleted"] == 1


def test_legacy_chunks_are_backfilled_as_shared(tmp_path, monkeypatch):
    path = str(tmp_path / "legacy")
    legacy = VectorStoreService(persist_directory=path, collection_name="old")
    legacy.collection.upsert(
        ids=["old-doc_0"],
        documents=["Indexed before access metadata existed."],
        embeddings=[[1.0, 0.0, 0.0]],
        metadatas=[{"document_id": "old-doc", "chunk_index": 0}],
    )

    # The backfill runs once per collection per process, as on app start.
    monkeypatch.setattr(
        "app.services.vector_store_service._backfilled_collections", set()
    )
    store = VectorStoreService(
        persist_directory=path,
        collection_name="old",
        embedding_model="old-model",
    )

    assert store.get_document_metadata("old-doc") == {
        "document_id": "old-doc",
        "chunk_index": 0,
        "visibility": "shared",
        "owner_id": "",
        "source": "api",
        "doc_type": "text",
        "chunk_hash": text_hash("Indexed before access metadata existed."),
        "embedding_model": "old-model",
    }
    assert store.search(
        [1.0, 0.0, 0.0], where=build_search_filter(user_id="alice")
    )[0]["id"] == "old-doc_0"


# --- API ---


def login(client, email: str) -> dict:
    payload = {"email": email, "password": "StrongPass123!"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post("/api/auth/login", json=payload)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def rag_api(client, isolated_rag_service, monkeypatch):
    monkeypatch.setattr("app.routes.rag.rag_service", isolated_rag_service)
    return client


def search(client, headers, **body) -> set[str]:
    response = client.post(
        "/api/rag/search", headers=headers, json={"query": "notes", **body}
    )
    assert response.status_code == 200
    return {
        result["metadata"]["document_id"]
        for result in response.json()["results"]
    }


def test_upload_markdown_is_private_to_the_uploader(rag_api):
    alice = login(rag_api, "alice-upload@example.com")
    bob = login(rag_api, "bob-upload@example.com")

    response = rag_api.post(
        "/api/rag/upload",
        headers=alice,
        files={"file": ("guide.md", b"# Guide\n\nAlice's notes.", "text/markdown")},
        data={"document_id": "alice-guide"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "alice-guide",
        "status": "indexed",
        "chunks_indexed": 1,
        "chunks_embedded": 1,
        "source": "guide.md",
        "doc_type": "markdown",
        "visibility": "private",
    }
    assert search(rag_api, alice) == {"alice-guide"}
    assert search(rag_api, alice, doc_type="pdf") == set()
    assert search(rag_api, bob) == set()


def test_upload_pdf(rag_api):
    alice = login(rag_api, "alice-pdf@example.com")

    response = rag_api.post(
        "/api/rag/upload",
        headers=alice,
        files={"file": ("manual.pdf", make_pdf("PDF notes"), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["doc_type"] == "pdf"
    assert search(rag_api, alice, source="manual.pdf") == {
        response.json()["document_id"]
    }


def test_upload_rejects_unsupported_and_oversized_files(rag_api, monkeypatch):
    alice = login(rag_api, "alice-reject@example.com")

    unsupported = rag_api.post(
        "/api/rag/upload",
        headers=alice,
        files={"file": ("photo.png", b"\x89PNG", "image/png")},
    )
    monkeypatch.setattr("app.routes.rag.RAG_MAX_UPLOAD_BYTES", 10)
    oversized = rag_api.post(
        "/api/rag/upload",
        headers=alice,
        files={"file": ("big.txt", b"x" * 11, "text/plain")},
    )

    assert unsupported.status_code == 400
    assert "Unsupported file type" in unsupported.json()["detail"]
    assert oversized.status_code == 413


def test_upload_requires_authentication(rag_api):
    response = rag_api.post(
        "/api/rag/upload",
        files={"file": ("notes.txt", b"text", "text/plain")},
    )

    assert response.status_code == 401


def test_user_cannot_overwrite_or_delete_another_users_document(rag_api):
    alice = login(rag_api, "alice-owner@example.com")
    bob = login(rag_api, "bob-intruder@example.com")

    created = rag_api.post(
        "/api/rag/index",
        headers=alice,
        json={"text": "Alice notes", "document_id": "alice-doc"},
    )
    overwrite = rag_api.post(
        "/api/rag/index",
        headers=bob,
        json={"text": "Bob takeover", "document_id": "alice-doc"},
    )
    delete = rag_api.delete("/api/rag/documents/alice-doc", headers=bob)

    assert created.status_code == 200
    assert overwrite.status_code == 403
    assert delete.status_code == 403
    assert search(rag_api, alice) == {"alice-doc"}
