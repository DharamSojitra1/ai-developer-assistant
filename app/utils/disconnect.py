"""Cancel request work when the client goes away (e.g. the Stop button).

Starlette keeps running a normal (non-streaming) endpoint after the client
disconnects, so an abandoned agent run would keep calling the LLM, spend
tokens, and save an answer nobody receives.
"""

import asyncio
import contextlib
from collections.abc import Awaitable
from typing import TypeVar

from fastapi import Request

T = TypeVar("T")

DISCONNECT_POLL_SECONDS = 0.5


class ClientDisconnectedError(Exception):
    """The client disconnected and the work was cancelled."""


async def run_until_disconnect(
    request: Request,
    work: Awaitable[T],
    poll_seconds: float = DISCONNECT_POLL_SECONDS,
) -> T:
    """Await `work`, cancelling it if the client disconnects first.

    Raises ClientDisconnectedError after the cancelled work has unwound.
    """
    task = asyncio.ensure_future(work)

    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=poll_seconds)

            if done:
                return task.result()

            if await request.is_disconnected():
                task.cancel()

                with contextlib.suppress(asyncio.CancelledError):
                    await task

                raise ClientDisconnectedError
    except asyncio.CancelledError:
        task.cancel()
        raise
