"""Reusable FastAPI dependencies for protecting routes.

Usage in a route:
    user = Depends(get_current_user)                 # any logged-in user
    user = Depends(require_permission("user:read"))  # needs a permission
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.permissions import has_permission
from app.core.security import ACCESS_TOKEN, decode_token
from app.db import db_queries
from app.db.model import User

# Reads the "Authorization: Bearer <token>" header and adds the Authorize button to /docs.
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    """Return the logged-in user, or stop with 401.

    The user is loaded from the database on every request, so a deactivated
    user is locked out of auth-service immediately, not when the token expires.
    """
    payload = decode_token(credentials.credentials, ACCESS_TOKEN)

    user = await db_queries.get_by_id(payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or deactivated")
    return user


def require_permission(permission: str):
    """Build a dependency that only lets through users whose role has `permission`."""

    async def check_permission(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return user

    return check_permission
