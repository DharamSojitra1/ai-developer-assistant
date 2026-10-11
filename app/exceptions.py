from fastapi import Request
from fastapi.responses import JSONResponse
from app.custom_exceptions import AppException
from app.utils.log_context import get_log_context, logged_error_context
from pymongo.errors import ConnectionFailure
import logging

logger = logging.getLogger(__name__)


def log_request_error(
    message: str,
    request: Request,
    exc: Exception,
    request_id: str,
) -> None:
    """Log with request, user, run, and step context.

    If the error was already logged with its traceback (e.g. by a failed
    agent run), only the context is logged here.
    """
    already_logged = logged_error_context(exc)

    logger.error(
        message,
        extra={
            **get_log_context(),
            **(already_logged or {}),
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
        },
        exc_info=(
            None
            if already_logged is not None
            else (type(exc), exc, exc.__traceback__)
        ),
    )


async def app_exception_handler(
    request: Request,
    exc: AppException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
            },
        },    
    )

async def database_unavailable_handler(
    request: Request,
    exc: ConnectionFailure,
):
    request_id = getattr(
        request.state,
        "request_id",
        "unknown",
    )

    log_request_error("Database unavailable", request, exc, request_id)

    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": (
                    "The database is temporarily unavailable. "
                    "Please try again shortly."
                ),
            },
            "request_id": request_id,
        },
        headers={"Retry-After": "5"},
    )

async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    request_id = getattr(
        request.state,
        "request_id",
        "unknown",
    )

    log_request_error("Unhandled application exception", request, exc, request_id)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
            },
            "request_id": request_id,
        },
    )
