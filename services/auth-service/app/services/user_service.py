"""Business rules for admin user management."""

import math

from fastapi import HTTPException, status

from app.core.permissions import Role
from app.core.security import hash_password
from app.db import user_repository
from app.db.models import new_user_document, user_to_out
from app.schemas.user import UserCreate, UserUpdate


async def _get_or_404(user_id: str) -> dict:
    user = await user_repository.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


def _block_self_change(user_id: str, admin: dict, message: str) -> None:
    """Stop admins from locking themselves out (deactivating or demoting themselves)."""
    if user_id == str(admin["_id"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, message)


async def create_user(data: UserCreate, admin: dict) -> dict:
    user_doc = new_user_document(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        warehouse_ids=data.warehouse_ids,
        created_by=str(admin["_id"]),
    )
    try:
        user = await user_repository.create(user_doc)
    except user_repository.DuplicateEmailError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    return user_to_out(user)


async def list_users(page: int, page_size: int, role: Role | None) -> dict:
    skip = (page - 1) * page_size  # page 1 skips 0, page 2 skips page_size, ...
    users = await user_repository.list_users(role, skip, page_size)
    total = await user_repository.count(role)
    return {
        "items": [user_to_out(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


async def get_user(user_id: str) -> dict:
    return user_to_out(await _get_or_404(user_id))


async def update_user(user_id: str, data: UserUpdate, admin: dict) -> dict:
    # exclude_unset: skip fields the client didn't send; exclude_none: skip explicit nulls
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    if fields.get("is_active") is False:
        _block_self_change(user_id, admin, "You cannot deactivate your own account")

    user = await user_repository.update(user_id, fields)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user_to_out(user)


async def change_role(user_id: str, role: Role, admin: dict) -> dict:
    """Takes effect immediately in auth-service, and in other services with the user's next token."""
    _block_self_change(user_id, admin, "You cannot change your own role")
    user = await user_repository.update(user_id, {"role": str(role)})
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user_to_out(user)


async def deactivate_user(user_id: str, admin: dict) -> dict:
    """Soft delete: keep the record but block login and API access."""
    _block_self_change(user_id, admin, "You cannot deactivate your own account")
    user = await user_repository.update(user_id, {"is_active": False})
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user_to_out(user)
