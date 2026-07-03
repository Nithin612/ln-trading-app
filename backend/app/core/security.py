import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError  # noqa: F401 — re-exported for callers

from app.core.config import settings

# ── Password hashing ────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Timestamp helper ─────────────────────────────────────────────────────────

def utc_now() -> datetime:
    return datetime.now(UTC)


# ── JWT creation ─────────────────────────────────────────────────────────────

def create_access_token(user_id: int, email: str, role: str) -> str:
    """Short-lived token stored in JS memory, never in localStorage."""
    expire = utc_now() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "jti": secrets.token_hex(16),
        "exp": expire,
        "iat": utc_now(),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, session_id: int) -> tuple[str, str]:
    """Long-lived token set in httpOnly cookie.

    Returns (encoded_token, jti).  Only the jti hash is stored in the DB —
    the raw token is never persisted.
    """
    jti = secrets.token_hex(32)
    expire = utc_now() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "session_id": session_id,
        "jti": jti,
        "type": "refresh",
        "exp": expire,
        "iat": utc_now(),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


# ── JWT decoding ─────────────────────────────────────────────────────────────

def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT.  Raises jwt.InvalidTokenError on any failure."""
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


# ── Token hashing (for DB storage) ───────────────────────────────────────────

def hash_token(value: str) -> str:
    """One-way SHA-256 hash for storing JTI values in the DB."""
    return hashlib.sha256(value.encode()).hexdigest()
