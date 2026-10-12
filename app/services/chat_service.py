import re

from app.config import MOCK_MODE
from app.services.llm_service import create_rag_chain, create_streaming_rag_chain
from app.services.rag_service import RAGService
from app.database import get_recent_chat_history
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.guards.injection import screen_input

_CLOSING_TAG = re.compile(r"</\s*document", re.IGNORECASE)

_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """The shared RAG service, created on first use.

    Creating one loads the reranker model and opens the vector store, which
    takes seconds and blocks, so it must not happen per request.
    """
    global _rag_service

    if _rag_service is None:
        _rag_service = RAGService()

    return _rag_service


def _escape_attribute(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_context(chunks: list[dict]) -> str:
    """Wrap each retrieved chunk in its own <document> block.

    Retrieved text is untrusted: a chunk containing `</document>` is escaped
    so it cannot close its block and pose as instructions outside it.
    """
    blocks = []

    for chunk in chunks:
        document_id = str(
            chunk.get("metadata", {}).get("document_id", "unknown")
        )
        screen_input(
            chunk["text"],
            "retrieved_document",
            document_id=document_id,
        )
        text = _CLOSING_TAG.sub("&lt;/document", chunk["text"])
        blocks.append(
            f'<document id="{_escape_attribute(document_id)}">\n'
            f"{text}\n</document>"
        )

    return "\n\n".join(blocks)


async def generate_response(
    message: str,
    temperature: float,
    max_tokens: int,
    user_id: str,
    conversation_id: str | None = None,
) -> dict:

    if MOCK_MODE:
        return {
            "response": f"Mock response: {message}",
            "sources": [],
        }

    rag_service = get_rag_service()
    retrieved_chunks = []

    async def retrieve_context(inputs: dict) -> str:
        chunks = await rag_service.retrieve(
            query=inputs["message"],
            top_k=3,
            user_id=inputs["user_id"],
        )

        retrieved_chunks.extend(chunks)

        return format_context(chunks)

    async def retrieve_history(inputs: dict) -> list:
        history = await get_recent_chat_history(
            user_id=inputs["user_id"],
            limit=10,
            conversation_id=conversation_id,
        )

        messages = []

        for item in history:
            messages.append(("human", item["message"]))
            messages.append(("ai", item["response"]))

        return messages

    rag_chain = (
        RunnablePassthrough.assign(
            context=RunnableLambda(retrieve_context),
            chat_history=RunnableLambda(retrieve_history),
        )
        | create_rag_chain(
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )

    answer = await rag_chain.ainvoke({
        "message": message,
        "user_id": user_id,
    })

    sources = [
        {
            "document_id": str(
                chunk.get("metadata", {}).get(
                    "document_id", "unknown"
                )
            ),
            "text": chunk["text"],
        }
        for chunk in retrieved_chunks
    ]

    return {
        "response": answer,
        "sources": sources,
    }

async def generate_streaming_response(
    message: str,
    temperature: float,
    max_tokens: int,
    user_id: str,
    conversation_id: str | None = None,
):
    if MOCK_MODE:
        yield f"Mock response: {message}"
        return

    rag_service = get_rag_service()

    retrieved_chunks = []

    # Retrieve RAG context
    chunks = await rag_service.retrieve(
        query=message,
        top_k=3,
        user_id=user_id,
    )

    retrieved_chunks.extend(chunks)

    context = format_context(chunks)

    # Retrieve conversation history
    history = await get_recent_chat_history(
        user_id=user_id,
        limit=10,
        conversation_id=conversation_id,
    )

    chat_history = []

    for item in history:
        chat_history.append(
            ("human", item["message"])
        )
        chat_history.append(
            ("ai", item["response"])
        )

    # Create streaming chain
    streaming_chain = create_streaming_rag_chain(
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Stream response chunks
    async for chunk in streaming_chain.astream({
        "message": message,
        "context": context,
        "chat_history": chat_history,
    }):
        yield chunk