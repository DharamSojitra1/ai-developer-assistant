import json
from langchain_core.tools import tool
from app.services.rag_service import RAGService

rag_service = RAGService()

@tool
async def search_knowledge_base(query: str) -> str:
    """
    Search the knowledge base for relevant information.

    Use this tool when the user asks about information
    that may be available in the application's documents
    or knowledge base.
    """
    
    results = await rag_service.retrieve(
        query=query,
        top_k=3
    )

    if not results:
        return json.dumps({
            "results": []
        })

    return json.dumps({
            "results": [
                {
                    "document_id": str(
                        result.get("metadata", {}).get(
                            "document_id",
                            "unknown",
                        )
                    ),
                    "text": result["text"],
                }
                for result in results
            ]
        })