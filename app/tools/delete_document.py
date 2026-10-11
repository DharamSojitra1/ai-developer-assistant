"""Delete one of the current user's knowledge-base documents.

Sensitive: it permanently removes data, so the agent graph pauses for the
user's approval first (see `make_approval_node`). The tool re-checks that
approval itself, so it never deletes without a recorded "yes" for this exact
tool call, even if called from a graph without an approval step.
"""

import asyncio
from typing import Annotated

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from pydantic import Field

from app.services.rag_service import DocumentPermissionError, Requester
from app.tools.rag_search import rag_service
from app.tools.schemas import NonBlankStr, StrictToolInput
from app.tools.tool_result import (
    handle_validation_error,
    tool_error,
    tool_success,
    with_timeout,
)
from app.utils.agent_logger import logger
from app.utils.log_context import user_id_var


class DeleteDocumentInput(StrictToolInput):
    document_id: NonBlankStr = Field(
        ...,
        max_length=128,
        description="ID of the user's own knowledge-base document to delete.",
    )
    tool_call_id: Annotated[str, InjectedToolCallId]
    state: Annotated[dict, InjectedState]


def _current_requester() -> Requester | None:
    user_id = user_id_var.get()
    # Never an admin here: the agent may only delete the user's own documents.
    return Requester(user_id=user_id) if user_id else None


async def describe_delete_request(args: dict) -> dict:
    """What the user is asked to approve; reveals nothing they do not own."""
    document_id = str(args.get("document_id", ""))
    requester = _current_requester()
    metadata = None

    if requester is not None and document_id.strip():
        metadata = await asyncio.to_thread(
            rag_service.vector_store.get_document_metadata,
            document_id,
        )

    owned = (
        metadata is not None
        and metadata.get("visibility") == "private"
        and metadata.get("owner_id") == requester.user_id
    )

    return {
        "action": "delete_document",
        "document_id": document_id,
        "source": metadata.get("source") if owned else None,
        "found": owned,
    }


@tool(args_schema=DeleteDocumentInput)
@with_timeout("Deleting the document timed out. Try again later.")
async def delete_my_document(
    document_id: str,
    tool_call_id: str,
    state: dict,
) -> str:
    """
    Permanently delete one of the current user's own knowledge-base
    documents by its document ID. The user is asked to approve the deletion
    before it happens. Only use this when the user explicitly asks to
    delete a document.
    """
    if (state.get("approvals") or {}).get(tool_call_id) is not True:
        return tool_error("The user did not approve deleting this document.")

    requester = _current_requester()

    if requester is None:
        return tool_error("No user is associated with this request.")

    try:
        result = await asyncio.to_thread(
            rag_service.delete_document,
            document_id,
            requester,
        )
    except DocumentPermissionError:
        return tool_error("You can only delete your own documents.")
    except ValueError as exc:
        return tool_error(str(exc))
    except Exception:
        logger.exception("Document deletion tool failed")
        return tool_error("Deleting the document failed.")

    if result["chunks_deleted"] == 0:
        return tool_error(f"No document with ID '{document_id}' was found.")

    return tool_success(result)


delete_my_document.handle_validation_error = handle_validation_error
