from app.schemas import RefreshTokenRequest
import email
from fastapi import APIRouter, HTTPException, Request, status
from app.schemas import UserRegisterRequest, UserResponse, TokenResponse
from app.database import create_user, get_user_by_email, save_refresh_token, revoke_refresh_token, save_refresh_token
from app.security import hash_password, verify_password, create_access_token, create_refresh_token, hash_refresh_token, decode_token
from app.config import RATE_LIMIT_AUTH, REFRESH_TOKEN_EXPIRE_DAYS
from app.limiter import ip_key, limiter
from datetime import datetime, timedelta, timezone


router = APIRouter()

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit(RATE_LIMIT_AUTH, key_func=ip_key)
async def register_user(request: Request, body: UserRegisterRequest):
    email = str(body.email).lower()

    hashed_password = hash_password(body.password)

    user = await create_user(
        email = email,
        hashed_password = hashed_password
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    return user

@router.post(
    "/login",
    response_model=TokenResponse
)
@limiter.limit(RATE_LIMIT_AUTH, key_func=ip_key)
async def login_user(request: Request, body: UserRegisterRequest):
    email = str(body.email).lower()

    user = await get_user_by_email(email)

    if not user or not verify_password(
        body.password,
        user["hashed_password"]
    ):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    user_id = str(user["_id"])

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    
    refresh_expires_at = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    await save_refresh_token(
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_expires_at,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post(
    "/refresh",
    response_model=TokenResponse
)
@limiter.limit(RATE_LIMIT_AUTH, key_func=ip_key)
async def refresh_access_token(request: Request, body: RefreshTokenRequest):
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invaild or expired refresh token"
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid refresh token"
        )

    old_token_hash = hash_refresh_token(body.refresh_token)
    old_token = await revoke_refresh_token(old_token_hash)

    if not old_token or old_token["user_id"] != user_id:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Refresh token is revoked or invalid"
        )

    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    await save_refresh_token(
        user_id=user_id,
        token_hash=hash_refresh_token(new_refresh_token),
        expires_at=expires_at,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }

@router.post("/logout")
@limiter.limit(RATE_LIMIT_AUTH, key_func=ip_key)
async def logout_user(request: Request, body: RefreshTokenRequest):
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    token_hash = hash_refresh_token(body.refresh_token)

    revoked_token = await revoke_refresh_token(token_hash)

    if not revoked_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is already revoked or invalid",
        )

    return {"message": "Logged out successfully"}