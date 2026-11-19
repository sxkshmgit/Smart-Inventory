"""/auth/users endpoints: admin user management.

Every route is protected by a permission from core/permissions.py.
`dependencies=[...]` runs the check when the route doesn't need the user object itself.
"""

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Role
from app.routes.deps import require_permission
from app.schemas.user import RoleUpdate, UserCreate, UserList, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, admin: dict = Depends(require_permission("user:create"))):
    return await user_service.create_user(data, admin)


@router.get("", response_model=UserList, dependencies=[Depends(require_permission("user:read"))])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Role | None = None,
):
    return await user_service.list_users(page, page_size, role)


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(require_permission("user:read"))])
async def get_user(user_id: str):
    return await user_service.get_user(user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, data: UserUpdate, admin: dict = Depends(require_permission("user:update"))
):
    return await user_service.update_user(user_id, data, admin)


@router.patch("/{user_id}/role", response_model=UserOut)
async def change_role(
    user_id: str, data: RoleUpdate, admin: dict = Depends(require_permission("user:assign_role"))
):
    return await user_service.change_role(user_id, data.role, admin)


@router.delete("/{user_id}", response_model=UserOut)
async def deactivate_user(user_id: str, admin: dict = Depends(require_permission("user:delete"))):
    return await user_service.deactivate_user(user_id, admin)
