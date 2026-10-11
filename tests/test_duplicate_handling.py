import pytest

from app.services.document_service import Chunk
from app.services.rag_service import DuplicateDocumentError, Requester

ALICE = Requester(user_id="alice")
BOB = Requester(user_id="bob")
ADMIN = Requester(user_id="admin", is_admin=True)

HANDBOOK = "Our refund window is 30 days.\n\nShipping takes 5 business days."


def embedded_texts(service) -> list[str]:
    calls = service.embedding_service.embed_documents.await_args_list
    return [text for call in calls for text in call.args[0]]


@pytest.mark.asyncio
async def test_reindexing_identical_content_is_a_no_op(isolated_rag_service):
    service = isolated_rag_service
    first = await service.index_document(HANDBOOK, "handbook")
    second = await service.index_document(HANDBOOK, "handbook")

    assert first["status"] == "indexed"
    assert second == {**first, "status": "unchanged", "chunks_embedded": 0}
    assert service.embedding_service.embed_documents.await_count == 1


@pytest.mark.asyncio
async def test_metadata_change_reindexes_without_re_embedding(isolated_rag_service):
    service = isolated_rag_service
    await service.index_document(HANDBOOK, "handbook")

    result = await service.index_document(HANDBOOK, "handbook", source="v2.txt")

    assert result["status"] == "indexed"
    assert result["chunks_embedded"] == 0
    assert service.vector_store.get_document_metadata("handbook")["source"] == "v2.txt"


@pytest.mark.asyncio
async def test_identical_content_under_another_id_is_rejected(isolated_rag_service):
    service = isolated_rag_service
    await service.index_document(HANDBOOK, "handbook")

    with pytest.raises(DuplicateDocumentError) as error:
        await service.index_document(f"  {HANDBOOK}\r\n", "handbook-copy")

    assert error.value.existing_document_id == "handbook"
    assert service.vector_store.get_document_metadata("handbook-copy") is None


@pytest.mark.asyncio
async def test_duplicates_are_scoped_to_documents_the_requester_can_see(
    isolated_rag_service,
):
    service = isolated_rag_service
    await service.index_document(
        HANDBOOK, "bob-copy", visibility="private", requester=BOB
    )

    # Bob's private copy must neither block nor be revealed to Alice.
    result = await service.index_document(
        HANDBOOK, "alice-copy", visibility="private", requester=ALICE
    )

    assert result["status"] == "indexed"

    with pytest.raises(DuplicateDocumentError):
        await service.index_document(
            HANDBOOK, "alice-copy-2", visibility="private", requester=ALICE
        )


@pytest.mark.asyncio
async def test_private_upload_of_shared_content_is_a_duplicate(isolated_rag_service):
    service = isolated_rag_service
    await service.index_document(
        HANDBOOK, "handbook", visibility="shared", requester=ADMIN
    )

    with pytest.raises(DuplicateDocumentError, match="'handbook'"):
        await service.index_document(
            HANDBOOK, "mine", visibility="private", requester=ALICE
        )


@pytest.mark.asyncio
async def test_repeated_chunks_within_a_document_are_stored_once(
    isolated_rag_service, monkeypatch
):
    service = isolated_rag_service
    monkeypatch.setattr(
        "app.services.rag_service.chunk_document",
        lambda text, doc_type: [
            Chunk("Header boilerplate."),
            Chunk("Unique body."),
            Chunk("Header boilerplate."),
        ],
    )

    result = await service.index_document("ignored", "doc")

    assert result["chunks_indexed"] == 2
    assert embedded_texts(service) == ["Header boilerplate.", "Unique body."]


@pytest.mark.asyncio
async def test_editing_a_document_only_embeds_changed_chunks(
    isolated_rag_service, monkeypatch
):
    service = isolated_rag_service
    chunks = [Chunk("Section one."), Chunk("Section two.")]
    monkeypatch.setattr(
        "app.services.rag_service.chunk_document",
        lambda text, doc_type: chunks,
    )
    await service.index_document("version 1", "doc")

    chunks[1] = Chunk("Section two, revised.")
    result = await service.index_document("version 2", "doc")

    assert result["chunks_embedded"] == 1
    assert embedded_texts(service) == [
        "Section one.",
        "Section two.",
        "Section two, revised.",
    ]
    stored = service.vector_store.collection.get(where={"document_id": "doc"})
    assert sorted(stored["documents"]) == ["Section one.", "Section two, revised."]


@pytest.mark.asyncio
async def test_changed_chunk_settings_rechunk_unchanged_content(
    isolated_rag_service, monkeypatch
):
    service = isolated_rag_service
    await service.index_document(HANDBOOK, "handbook")

    monkeypatch.setattr(
        "app.services.rag_service.chunking_signature",
        lambda doc_type: "recursive:400:40",
    )
    result = await service.index_document(HANDBOOK, "handbook")

    assert result["status"] == "indexed"
    assert (
        service.vector_store.get_document_metadata("handbook")["chunking"]
        == "recursive:400:40"
    )


def login(client, email: str) -> dict:
    payload = {"email": email, "password": "StrongPass123!"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post("/api/auth/login", json=payload)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_api_returns_409_for_duplicate_and_unchanged_status(
    client, isolated_rag_service, monkeypatch
):
    monkeypatch.setattr("app.routes.rag.rag_service", isolated_rag_service)
    alice = login(client, "alice-dup@example.com")

    def index(document_id):
        return client.post(
            "/api/rag/index",
            headers=alice,
            json={"text": HANDBOOK, "document_id": document_id},
        )

    first = index("notes")
    again = index("notes")
    copy = index("notes-copy")

    assert first.json()["status"] == "indexed"
    assert again.json()["status"] == "unchanged"
    assert copy.status_code == 409
    assert "'notes'" in copy.json()["detail"]
