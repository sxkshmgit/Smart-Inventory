"""/auth/users endpoints and their business rules: admin user management.

Every route is protected by a permission from core/permissions.py.
`dependencies=[...]` runs the check when the route doesn't need the user object itself.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Role
from app.core.security import hash_password
from app.db import db_queries
from app.db.helpers import new_user_document, user_to_out
from app.db.model import RoleUpdate, UserCreate, UserList, UserOut, UserUpdate
from app.routes.deps import require_permission

router = APIRouter(prefix="/users", tags=["Users"])


async def _get_or_404(user_id: str) -> dict:
    user = await db_queries.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


def _block_self_change(user_id: str, admin: dict, message: str) -> None:
    """Stop admins from locking themselves out (deactivating or demoting themselves)."""
    if user_id == str(admin["_id"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, message)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, admin: dict = Depends(require_permission("user:create"))):
    user_doc = new_user_document(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        warehouse_ids=data.warehouse_ids,
        created_by=str(admin["_id"]),
    )
    try:
        user = await db_queries.create(user_doc)
    except db_queries.DuplicateEmailError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    return user_to_out(user)


@router.get("", response_model=UserList, dependencies=[Depends(require_permission("user:read"))])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Role | None = None,
):
    skip = (page - 1) * page_size  # page 1 skips 0, page 2 skips page_size, ...
    users = await db_queries.list_users(role, skip, page_size)
    total = await db_queries.count(role)
    return {
        "items": [user_to_out(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(require_permission("user:read"))])
async def get_user(user_id: str):
    return user_to_out(await _get_or_404(user_id))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, data: UserUpdate, admin: dict = Depends(require_permission("user:update"))
):
    # exclude_unset: skip fields the client didn't send; exclude_none: skip explicit nulls
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    if fields.get("is_active") is False:
        _block_self_change(user_id, admin, "You cannot deactivate your own account")

    user = await db_queries.update(user_id, fields)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user_to_out(user)


@router.patch("/{user_id}/role", response_model=UserOut)
async def change_role(
    user_id: str, data: RoleUpdate, admin: dict = Depends(require_permission("user:assign_role"))
):
    """Takes effect immediately in auth-service, and in other services with the user's next token."""
    _block_self_change(user_id, admin, "You cannot change your own role")
    user = await db_queries.update(user_id, {"role": str(data.role)})
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user_to_out(user)


@router.delete("/{user_id}", response_model=UserOut)
async def deactivate_user(user_id: str, admin: dict = Depends(require_permission("user:delete"))):
    """Soft delete: keep the record but block login and API access."""
    _block_self_change(user_id, admin, "You cannot deactivate your own account")
    user = await db_queries.update(user_id, {"is_active": False})
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user_to_out(user)
