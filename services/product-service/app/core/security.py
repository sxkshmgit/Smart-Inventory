"""Verifying the JWT access tokens issued by auth-service.

This service never creates tokens or handles passwords: it only checks them.
"""

import jwt
from fastapi import HTTPException, status

from app.core.config import settings

ACCESS_TOKEN = "access"


def decode_token(token: str, expected_type: str) -> dict:
    """Verify signature, expiry and type. Return the payload or raise 401."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    # Stops a refresh token from being used as an access token.
    if payload.get("type") != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")

    return payload
