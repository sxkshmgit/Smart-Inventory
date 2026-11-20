"""Reusable FastAPI dependencies for protecting routes.

Usage in a route:
    user = Depends(get_current_user)                    # any logged-in user
    user = Depends(require_permission("product:read"))  # needs a permission
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import ACCESS_TOKEN, decode_token

# Reads the "Authorization: Bearer <token>" header and adds the Authorize button to /docs.
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Return the logged-in user, read from the token, or stop with 401.

    There is no user database here: we trust the token signed by auth-service.
    """
    payload = decode_token(credentials.credentials, ACCESS_TOKEN)
    return {
        "id": payload["sub"],
        "role": payload["role"],
        "permissions": payload.get("permissions", []),
    }


def require_permission(permission: str):
    """Build a dependency that only lets through users whose token has `permission`."""

    async def check_permission(user: dict = Depends(get_current_user)) -> dict:
        if permission not in user["permissions"]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return user

    return check_permission
