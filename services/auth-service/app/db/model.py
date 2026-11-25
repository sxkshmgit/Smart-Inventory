"""What the API accepts (requests) and returns (responses).

FastAPI checks every request against these models and answers 422 if it doesn't fit.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.permissions import Role


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


class UserCreate(UserRegister):
    """Body of POST /users (admin only). Same as register, plus role and warehouses."""

    role: Role = Role.VIEWER
    warehouse_ids: list[str] = []


class UserUpdate(BaseModel):
    """Body of PATCH /users/{id}. Every field is optional: only sent fields change."""

    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    warehouse_ids: list[str] | None = None
    is_active: bool | None = None


class RoleUpdate(BaseModel):
    role: Role


class LoginRequest(BaseModel):
    """Body of POST /auth/login. No strength rules here, so login never reveals them."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """A user as returned by the API. There is deliberately no password field."""

    id: str
    email: EmailStr
    full_name: str
    role: Role
    warehouse_ids: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


class UserList(BaseModel):
    items: list[UserOut]
    total: int  # users matching the filter, across all pages
    page: int
    page_size: int
    pages: int
