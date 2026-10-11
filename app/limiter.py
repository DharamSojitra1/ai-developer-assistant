from jwt import InvalidTokenError
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import RATE_LIMIT_ENABLED, RATE_LIMIT_STORAGE_URI
from app.security import decode_token


def ip_key(request: Request) -> str:
    return f"ip:{get_remote_address(request)}"


def rate_limit_key(request: Request) -> str:
    """Bucket per user for authenticated requests, otherwise per IP.

    Only the token's signature and expiry are checked here (no database
    lookup); routes still authenticate the user properly. A forged or
    expired token falls back to the IP bucket.
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")

    if scheme.lower() == "bearer" and token:
        try:
            payload = decode_token(token)
        except InvalidTokenError:
            payload = {}

        if payload.get("type") == "access" and payload.get("sub"):
            return f"user:{payload['sub']}"

    return ip_key(request)


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=RATE_LIMIT_STORAGE_URI,
    enabled=RATE_LIMIT_ENABLED,
)
