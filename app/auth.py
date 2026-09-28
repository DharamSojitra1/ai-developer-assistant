from requests import status_codes
import secrets

from fastapi import Header, HTTPException, status
from app.config import API_KEY

async def verify_api_key(
    x_api_key: str = Header(...)
):
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Api key"
        )