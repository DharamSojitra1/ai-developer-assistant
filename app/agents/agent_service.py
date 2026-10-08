import json
from langchain_core.messages import AIMessageChunk, ToolMessage
from app.database import get_recent_chat_history, save_chat_history
from app.agents.calculator_agent import create_agent_graph
from app.utils.agent_logger import logger

async def build_agent_messages(
    user_id: str,
    message: str,
    limit: int = 10,
) -> list:

    history = await get_recent_chat_history(user_id, limit)

    messages = []

    for item in history:
        messages.append(
            ("human", item["message"])
        )
        messages.append(
            ("ai", item["response"])
        )

    messages.append(
        ("human", message)
    )

    return messages

async def generate_agent_response(
    user_id: str,
    message: str,
    model: str,
) -> dict:

    logger.info(
        "Agent execution started",
        extra={
            "user_id": user_id,
            "message_length": len(message),
        },
    )

    messages = await build_agent_messages(
        user_id=user_id,
        message=message,
    )

    graph = create_agent_graph(
        temperature=0,
        max_tokens=500,
    )

    result = await graph.ainvoke(
        {
            "messages": messages,
            "iteration_count": 0,
            "sources": [],
        }
    )

    final_message = result["messages"][-1]

    sources = []

    for tool_message in result["messages"]:
        if not isinstance(tool_message, ToolMessage):
            continue

        logger.info(
            "Agent tool executed",
            extra={
                "user_id": user_id,
                "tool_name": tool_message.name,
            },
        )

        if tool_message.name != "search_knowledge_base":
            continue

        try:
            tool_data = json.loads(tool_message.content)

            sources.extend(
                tool_data.get("results", [])
            )

        except (json.JSONDecodeError, TypeError):
            continue

    response = final_message.content

    await save_chat_history(
        user_id=user_id,
        message=message,
        response=response,
        model=model,
    )

    logger.info(
        "Agent execution completed",
        extra={
            "user_id": user_id,
            "message_length": len(message),
        },
    )

    return {
        "response": response,
        "sources": sources,
    }

async def stream_agent_response(
    user_id: str,
    message: str,
):
    messages = await build_agent_messages(
        user_id=user_id,
        message=message,
    )

    graph = create_agent_graph(
        temperature=0,
        max_tokens=500,
    )

    async for event in graph.astream(
        {
            "messages": messages,
            "iteration_count": 0,
            "sources": [],
        },
        stream_mode="messages",
    ):
        message_chunk, metadata = event

        # Skip tool outputs (e.g. the calculator's raw result) and
        # tool-call chunks; only stream the LLM's answer text.
        if metadata.get("langgraph_node") != "llm":
            continue

        if not isinstance(message_chunk, AIMessageChunk):
            continue

        if message_chunk.content and isinstance(message_chunk.content, str):
            yield message_chunk.content