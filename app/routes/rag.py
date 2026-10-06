from fastapi import APIRouter, HTTPException
from app.schemas import (
    IndexDocumentRequest,
    IndexDocumentResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.rag_service import RAGService

router = APIRouter()

rag_service = RAGService()

@router.post(
    "/index",
    response_model=IndexDocumentResponse
)
async def index_document(
    request: IndexDocumentRequest,
):
    try:
        result = await rag_service.index_document(
            text=request.text,
            document_id=request.document_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post(
    "/search",
    response_model=SearchResponse
)
async def search_documents(
    request: SearchRequest,
):
    try:
        results = await rag_service.retrieve(
            query=request.query,
            top_k=request.top_k
        )
        return {
            "results": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )