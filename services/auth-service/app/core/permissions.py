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
# Other services add their own later, e.g. "product:read", "product:write".
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "user:read",
        "user:create",
        "user:update",
        "user:delete",
        "user:assign_role",
    },
    Role.INVENTORY_MANAGER: set(),
    Role.WAREHOUSE_STAFF: set(),
    Role.FINANCE_STAFF: set(),
    Role.VIEWER: set(),
}


def get_permissions(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))


def has_permission(role: str, permission: str) -> bool:
    """True if the role is allowed to do `permission`."""
    return permission in ROLE_PERMISSIONS.get(role, set())
