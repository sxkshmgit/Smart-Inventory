"""/auth/users endpoints and their business rules: admin user management.

Every route is protected by a permission from core/permissions.py.
`dependencies=[...]` runs the check when the route doesn't need the user object itself.
Each request model sits right above the route that uses it. Responses are the
User model from db/model.py (its password hash is never included).
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.permissions import Role
from app.core.security import hash_password
from app.db import db_queries
from app.db.model import Page, User
from app.routes.auth import UserRegister
from app.routes.deps import require_permission

router = APIRouter(prefix="/users", tags=["Users"])


async def _get_or_404(user_id: str) -> User:
    user = await db_queries.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


def _block_self_change(user_id: str, admin: User, message: str) -> None:
    """Stop admins from locking themselves out (deactivating or demoting themselves)."""
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, message)


async def _save(user: User) -> User:
    saved = await db_queries.update(user)
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return saved


# ---------- create ----------
class UserCreate(UserRegister):
    """Body of POST /auth/users (admin only). Same as register, plus role and warehouses."""

    role: Role = Role.VIEWER
    warehouse_ids: list[str] = []


@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, admin: User = Depends(require_permission("user:create"))):
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        warehouse_ids=data.warehouse_ids,
        created_by=admin.id,
    )
    try:
        return await db_queries.create(user)
    except db_queries.DuplicateEmailError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")


# ---------- list ----------
@router.get("", response_model=Page[User], dependencies=[Depends(require_permission("user:read"))])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Role | None = None,
):
    skip = (page - 1) * page_size  # page 1 skips 0, page 2 skips page_size, ...
    users = await db_queries.list_users(role, skip, page_size)
    total = await db_queries.count(role)
    return {
        "items": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


# ---------- get ----------
@router.get("/{user_id}", response_model=User, dependencies=[Depends(require_permission("user:read"))])
async def get_user(user_id: str):
    return await _get_or_404(user_id)


# ---------- update ----------
class UserUpdate(BaseModel):
    """Body of PATCH /auth/users/{id}. Every field is optional: only sent fields change."""

    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    warehouse_ids: list[str] | None = None
    is_active: bool | None = None


@router.patch("/{user_id}", response_model=User)
async def update_user(user_id: str, data: UserUpdate, admin: User = Depends(require_permission("user:update"))):
    # exclude_unset: skip fields the client didn't send; exclude_none: skip explicit nulls
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    if fields.get("is_active") is False:
        _block_self_change(user_id, admin, "You cannot deactivate your own account")

    current = await _get_or_404(user_id)
    return await _save(current.model_copy(update=fields))


# ---------- change role ----------
class RoleUpdate(BaseModel):
    """Body of PATCH /auth/users/{id}/role."""

    role: Role


@router.patch("/{user_id}/role", response_model=User)
async def change_role(user_id: str, data: RoleUpdate, admin: User = Depends(require_permission("user:assign_role"))):
    """Takes effect immediately in auth-service, and in other services with the user's next token."""
    _block_self_change(user_id, admin, "You cannot change your own role")
    current = await _get_or_404(user_id)
    return await _save(current.model_copy(update={"role": str(data.role)}))


# ---------- deactivate ----------
@router.delete("/{user_id}", response_model=User)
async def deactivate_user(user_id: str, admin: User = Depends(require_permission("user:delete"))):
    """Soft delete: keep the record but block login and API access."""
    _block_self_change(user_id, admin, "You cannot deactivate your own account")
    current = await _get_or_404(user_id)
    return await _save(current.model_copy(update={"is_active": False}))
