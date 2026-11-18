from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.permissions import get_permissions

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"

# Argon2 is the hashing algorithm pwdlib recommends.
password_hasher = PasswordHash.recommended()


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    """Turn a plain password into a one-way hash. Only the hash is stored."""
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a login password against the stored hash."""
    return password_hasher.verify(plain_password, hashed_password)


# ---------- Tokens ----------

def _create_token(data: dict, expires_in: timedelta) -> str:
    """Add issue/expiry times to `data` and sign it with SECRET_KEY."""
    now = datetime.now(timezone.utc)
    payload = {**data, "iat": now, "exp": now + expires_in}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    data = {
        "sub": user_id,
        "role": role,
        "permissions": get_permissions(role),
        "type": ACCESS_TOKEN,
    }
    return _create_token(data, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: str) -> str:
    data = {"sub": user_id, "type": REFRESH_TOKEN}
    return _create_token(data, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str, expected_type: str) -> dict:
    """Verify signature, expiry and type. Return the payload or raise 401."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    # Stops a refresh token from being used as an access token, and vice versa.
    if payload.get("type") != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")

    return payload
