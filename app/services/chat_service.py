from app.config import MOCK_MODE
from app.services.llm_service import create_rag_chain, create_streaming_rag_chain
from app.services.rag_service import RAGService
from app.database import get_recent_chat_history
from langchain_core.runnables import RunnableLambda, RunnablePassthrough


async def generate_response(
    message: str,
    temperature: float,
    max_tokens: int,
    user_id: str,
) -> dict:

    if MOCK_MODE:
        return {
            "response": f"Mock response: {message}",
            "sources": [],
        }

    rag_service = RAGService()
    retrieved_chunks = []

    async def retrieve_context(inputs: dict) -> str:
        chunks = await rag_service.retrieve(
            query=inputs["message"],
            top_k=3,
        )

        retrieved_chunks.extend(chunks)

        return "\n\n".join(
            chunk["text"] for chunk in chunks
        )

    async def retrieve_history(inputs: dict) -> list:
        history = await get_recent_chat_history(
            user_id=inputs["user_id"],
            limit=10,
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
):
    if MOCK_MODE:
        yield f"Mock response: {message}"
        return

    rag_service = RAGService()

    retrieved_chunks = []

    # Retrieve RAG context
    chunks = await rag_service.retrieve(
        query=message,
        top_k=3,
    )

    retrieved_chunks.extend(chunks)

    context = "\n\n".join(
        chunk["text"]
        for chunk in chunks
    )

    # Retrieve conversation history
    history = await get_recent_chat_history(
        user_id=user_id,
        limit=10,
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