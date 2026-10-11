import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Request

from app.database import record_token_usage
from app.utils.log_context import bind_log_context
from app.utils.request_metrics import RequestMetrics, bind_request_metrics

REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")

request_logger = logging.getLogger("app.request")


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")

    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    metrics = RequestMetrics()
    started = time.perf_counter()

    async def finish(status_code: int) -> None:
        await finish_request(request, request_id, metrics, started, status_code)

    # The endpoint (including a streaming body) runs in a task that copies
    # this context, so every log it writes carries the request ID, and its
    # LLM calls add to `metrics`.
    with bind_log_context(request_id=request_id), bind_request_metrics(metrics):
        try:
            response = await call_next(request)
        except Exception:
            # The app-level handler turns this into a 500 response.
            await finish(500)
            raise

    response.headers["X-Request-ID"] = request_id

    # call_next returns once headers are ready; a streamed body is still
    # being produced, so the request only finishes after the last chunk.
    response.body_iterator = _then(
        response.body_iterator,
        lambda: finish(response.status_code),
    )

    return response


async def _then(
    body: AsyncIterator[bytes],
    on_complete: Callable[[], Awaitable[None]],
) -> AsyncIterator[bytes]:
    try:
        async for chunk in body:
            yield chunk
    finally:
        await on_complete()


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Reject request bodies over `max_bytes` with 413.

    Checks Content-Length up front, and also counts the bytes actually
    received, so chunked bodies without a length cannot bypass the limit.
    Pure ASGI, so the body is never buffered here.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")

        if declared is not None:
            try:
                too_large = int(declared) > self.max_bytes
            except ValueError:
                too_large = False

            if too_large:
                await self._reject(send)
                return

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()

            if message["type"] == "http.request":
                received += len(message.get("body", b""))

                if received > self.max_bytes:
                    raise _BodyTooLarge

            return message

        async def tracking_send(message):
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True

            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if response_started:
                raise
            await self._reject(send)

    async def _reject(self, send) -> None:
        body = json.dumps(
            {
                "success": False,
                "error": {
                    "code": "REQUEST_TOO_LARGE",
                    "message": (
                        f"Request body exceeds the {self.max_bytes} byte limit."
                    ),
                },
            }
        ).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def route_template(request: Request) -> str | None:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    path_regex = getattr(route, "path_regex", None)

    if template is None or path_regex is None:
        return template

    # Routes from included routers only know the path below the router
    # prefix, so recover the prefix from the part of the URL they matched.
    path = request.url.path

    for index, char in enumerate(path):
        if char == "/" and path_regex.match(path[index:]):
            return path[:index] + template

    return template


async def finish_request(
    request: Request,
    request_id: str,
    metrics: RequestMetrics,
    started: float,
    status_code: int,
) -> None:
    request_logger.log(
        logging.WARNING if status_code >= 500 else logging.INFO,
        "Request completed",
        extra={
            "request_id": request_id,
            "user_id": metrics.user_id,
            "method": request.method,
            "path": request.url.path,
            # The route template groups requests like /documents/{document_id}.
            "route": route_template(request),
            "status_code": status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "llm_calls": metrics.llm_calls,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "total_tokens": metrics.total_tokens,
        },
    )

    if metrics.user_id is None or metrics.llm_calls == 0:
        return

    try:
        await record_token_usage(
            user_id=metrics.user_id,
            llm_calls=metrics.llm_calls,
            input_tokens=metrics.input_tokens,
            output_tokens=metrics.output_tokens,
        )
    except Exception:
        # Usage accounting must never fail the request.
        request_logger.warning(
            "Failed to record token usage",
            extra={"request_id": request_id, "user_id": metrics.user_id},
            exc_info=True,
        )
