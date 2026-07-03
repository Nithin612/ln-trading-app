from datetime import timedelta

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    utc_now,
    verify_password,
)
from app.models.user import User, UserSession
from app.schemas.common import MessageResponse
from app.schemas.user import (
    AccessTokenResponse,
    LoginRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "refresh_token"
_COOKIE_PATH = "/api/v1/auth"
_COOKIE_MAX_AGE = settings.jwt_refresh_token_expire_days * 24 * 60 * 60


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path=_COOKIE_PATH,
        max_age=_COOKIE_MAX_AGE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path=_COOKIE_PATH)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Create DB session row first so we have its ID for the refresh token payload
    session = UserSession(
        user_id=user.id,
        refresh_token_hash="placeholder",  # updated below
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=utc_now() + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(session)
    await db.flush()  # get session.id without committing

    refresh_token, jti = create_refresh_token(user.id, session.id)
    session.refresh_token_hash = hash_token(jti)
    await db.commit()
    await db.refresh(session)

    access_token = create_access_token(user.id, user.email, user.role)
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=_COOKIE_NAME),
) -> AccessTokenResponse:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    try:
        payload = decode_token(refresh_token)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type",
        )

    session_id: int = int(payload["session_id"])
    jti: str = payload["jti"]

    result = await db.execute(select(UserSession).where(UserSession.id == session_id))
    session = result.scalar_one_or_none()

    if session is None or session.refresh_token_hash != hash_token(jti) or not session.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or has been revoked",
        )

    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user: User | None = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer active",
        )

    # Revoke old session and issue a new one (rotation)
    session.revoked_at = utc_now()

    new_session = UserSession(
        user_id=user.id,
        refresh_token_hash="placeholder",
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        expires_at=utc_now() + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(new_session)
    await db.flush()

    new_refresh_token, new_jti = create_refresh_token(user.id, new_session.id)
    new_session.refresh_token_hash = hash_token(new_jti)
    await db.commit()

    access_token = create_access_token(user.id, user.email, user.role)
    _set_refresh_cookie(response, new_refresh_token)

    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None, alias=_COOKIE_NAME),
) -> MessageResponse:
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            session_id = int(payload.get("session_id", 0))
            jti = payload.get("jti", "")
            result = await db.execute(
                select(UserSession).where(UserSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session and session.refresh_token_hash == hash_token(jti):
                session.revoked_at = utc_now()
                await db.commit()
        except (jwt.InvalidTokenError, ValueError):
            pass  # cookie was already invalid — still clear it

    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
