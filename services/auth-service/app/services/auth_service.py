"""Business rules for register, login and refresh."""

from fastapi import HTTPException, status

from app.core.permissions import Role
from app.core.security import (
    REFRESH_TOKEN,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import user_repository
from app.db.models import new_user_document, user_to_out
from app.schemas.user import LoginRequest, UserRegister


def _issue_tokens(user: dict) -> dict:
    user_id = str(user["_id"])
    return {
        "access_token": create_access_token(user_id, user["role"]),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


async def register(data: UserRegister) -> dict:
    user_doc = new_user_document(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=Role.VIEWER,
    )
    try:
        user = await user_repository.create(user_doc)
    except user_repository.DuplicateEmailError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    return user_to_out(user)


async def login(data: LoginRequest) -> dict:
    user = await user_repository.get_by_email(data.email)
    if user is None or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    # Checked after the password, so only the real owner learns the account is disabled.
    if not user["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    return _issue_tokens(user)


async def refresh(refresh_token: str) -> dict:
    payload = decode_token(refresh_token, REFRESH_TOKEN)

    user = await user_repository.get_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    if not user["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    return _issue_tokens(user)
