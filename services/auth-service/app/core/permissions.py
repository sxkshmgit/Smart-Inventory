"""Roles and what each role is allowed to do.

Every user has exactly one role. This file is the ONLY place that says which
permissions a role has. To change who can do what, edit ROLE_PERMISSIONS.
"""

from enum import StrEnum


class Role(StrEnum):
    """The five user roles from the project README."""

    ADMIN = "admin"
    INVENTORY_MANAGER = "inventory_manager"
    WAREHOUSE_STAFF = "warehouse_staff"
    FINANCE_STAFF = "finance_staff"
    VIEWER = "viewer"


# Permissions are plain strings in the form "<resource>:<action>".
# Other services check these from the token, e.g. product-service checks "product:create".
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "user:read",
        "user:create",
        "user:update",
        "user:delete",
        "user:assign_role",
        "product:read",
        "product:create",
        "product:update",
        "product:delete",
    },
    Role.INVENTORY_MANAGER: {
        "product:read",
        "product:create",
        "product:update",
    },
    Role.WAREHOUSE_STAFF: {"product:read"},
    Role.FINANCE_STAFF: {"product:read"},
    Role.VIEWER: {"product:read"},
}


def get_permissions(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))


def has_permission(role: str, permission: str) -> bool:
    """True if the role is allowed to do `permission`."""
    return permission in ROLE_PERMISSIONS.get(role, set())
