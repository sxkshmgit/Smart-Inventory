"""/auth endpoints and their business rules: register, login, refresh, me.

Each request model sits right above the route that uses it. Responses are the
User model from db/model.py (its password hash is never included).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

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
from app.db.model import User
from app.routes.deps import get_current_user

router = APIRouter(tags=["Auth"])


def _issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }


# ---------- register ----------
class UserRegister(BaseModel):
    """Body of POST /auth/register. No role field: new users are always viewers."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain an uppercase letter")
        if not any(c.islower() for c in value):
            raise ValueError("Password must contain a lowercase letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain a digit")
        return value


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister):
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=Role.VIEWER,
    )
    try:
        return await db_queries.create(user)
    except db_queries.DuplicateEmailError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")


# ---------- login ----------
class LoginRequest(BaseModel):
    """Body of POST /auth/login. No strength rules here, so login never reveals them."""

    email: EmailStr
    password: str


@router.post("/login")
async def login(data: LoginRequest):
    """Returns {access_token, refresh_token, token_type}."""
    user = await db_queries.get_by_email(data.email)
    if user is None or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    # Checked after the password, so only the real owner learns the account is disabled.
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    return _issue_tokens(user)


# ---------- refresh ----------
class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(data: RefreshRequest):
    """Returns a new {access_token, refresh_token, token_type}."""
    payload = decode_token(data.refresh_token, REFRESH_TOKEN)

    user = await db_queries.get_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    return _issue_tokens(user)


# ---------- me ----------
@router.get("/me", response_model=User)
async def me(user: User = Depends(get_current_user)):
    return user
