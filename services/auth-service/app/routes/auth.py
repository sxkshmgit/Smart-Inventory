"""/auth endpoints and their business rules: register, login, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.permissions import Role
from app.core.security import (
    REFRESH_TOKEN,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import db_queries
from app.db.helpers import new_user_document, user_to_out
from app.db.model import LoginRequest, RefreshRequest, TokenPair, UserOut, UserRegister
from app.routes.deps import get_current_user

router = APIRouter(tags=["Auth"])


def _issue_tokens(user: dict) -> dict:
    user_id = str(user["_id"])
    return {
        "access_token": create_access_token(user_id, user["role"]),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister):
    user_doc = new_user_document(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=Role.VIEWER,
    )
    try:
        user = await db_queries.create(user_doc)
    except db_queries.DuplicateEmailError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    return user_to_out(user)


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest):
    user = await db_queries.get_by_email(data.email)
    if user is None or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    # Checked after the password, so only the real owner learns the account is disabled.
    if not user["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest):
    payload = decode_token(data.refresh_token, REFRESH_TOKEN)

    user = await db_queries.get_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    if not user["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    return _issue_tokens(user)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return user_to_out(user)
