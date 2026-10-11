import asyncio
import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from app.config import RAG_MAX_TEXT_CHARS, RAG_MAX_UPLOAD_BYTES, RATE_LIMIT_RAG
from app.dependencies import get_current_user
from app.limiter import limiter
from app.schemas import (
    IndexDocumentRequest,
    IndexDocumentResponse,
    SearchRequest,
    SearchResponse,
    Visibility,
)
from app.services.ingestion_service import load_document
from app.services.rag_service import (
    DocumentPermissionError,
    DuplicateDocumentError,
    RAGService,
    Requester,
)

logger = logging.getLogger(__name__)

router = APIRouter()

rag_service = RAGService()


async def _index(
    text: str,
    document_id: str | None,
    source: str,
    doc_type: str,
    visibility: str,
    current_user: dict,
) -> dict:
    try:
        return await rag_service.index_document(
            text=text,
            document_id=document_id,
            source=source,
            doc_type=doc_type,
            visibility=visibility,
            requester=Requester.from_user(current_user),
        )
    except DocumentPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except DuplicateDocumentError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e
    except Exception:
        logger.exception("Document indexing failed")
        raise HTTPException(
            status_code=500,
            detail="Document indexing is temporarily unavailable.",
        )


@router.post(
    "/index",
    response_model=IndexDocumentResponse
)
@limiter.limit(RATE_LIMIT_RAG)
async def index_document(
    request: Request,
    body: IndexDocumentRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _index(
        text=body.text,
        document_id=body.document_id,
        source=body.source,
        doc_type=body.doc_type,
        visibility=body.visibility,
        current_user=current_user,
    )


@router.post(
    "/upload",
    response_model=IndexDocumentResponse
)
@limiter.limit(RATE_LIMIT_RAG)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="A .txt, .md, or .pdf file."),
    document_id: str | None = Form(default=None, min_length=1, max_length=128),
    visibility: Visibility = Form(default="private"),
    current_user: dict = Depends(get_current_user),
):
    data = await file.read(RAG_MAX_UPLOAD_BYTES + 1)

    if len(data) > RAG_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {RAG_MAX_UPLOAD_BYTES} byte limit.",
        )

    try:
        # PDF parsing is CPU-bound.
        document = await asyncio.to_thread(
            load_document,
            file.filename or "",
            data,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if len(document.text) > RAG_MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Extracted text exceeds the {RAG_MAX_TEXT_CHARS} character limit.",
        )

    return await _index(
        text=document.text,
        document_id=document_id,
        source=document.source,
        doc_type=document.doc_type,
        visibility=visibility,
        current_user=current_user,
    )


@router.post(
    "/search",
    response_model=SearchResponse
)
@limiter.limit(RATE_LIMIT_RAG)
async def search_documents(
    request: Request,
    body: SearchRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        results = await rag_service.retrieve(
            query=body.query,
            top_k=body.top_k,
            user_id=current_user["user_id"],
            source=body.source,
            doc_type=body.doc_type,
        )
        return {
            "results": results
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e
    except Exception:
        logger.exception("Document search failed")
        raise HTTPException(
            status_code=500,
            detail="Document search is temporarily unavailable.",
        )

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = rag_service.delete_document(
            document_id=document_id,
            requester=Requester.from_user(current_user),
        )
        return result
    except DocumentPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e
    except Exception:
        logger.exception("Document deletion failed")
        raise HTTPException(
            status_code=500,
            detail="Document deletion is temporarily unavailable.",
        )
