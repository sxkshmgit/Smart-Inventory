"""How a user is stored in the MongoDB `users` collection."""

from datetime import datetime, timezone


def new_user_document(
    email: str,
    hashed_password: str,
    full_name: str,
    role: str,
    warehouse_ids: list[str] | None = None,
    created_by: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "email": email.lower(),  # "A@x.com" and "a@x.com" are the same user
        "hashed_password": hashed_password,
        "full_name": full_name,
        "role": str(role),
        "warehouse_ids": warehouse_ids or [],
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_by": created_by,  # admin's id, or None if self-registered
    }


def user_to_out(doc: dict) -> dict:
    """The safe shape the API returns. Fields are copied one by one, so
    hashed_password (or anything else not listed) can never leak."""
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "full_name": doc["full_name"],
        "role": doc["role"],
        "warehouse_ids": doc.get("warehouse_ids", []),
        "is_active": doc.get("is_active", True),
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        "created_by": doc.get("created_by"),
    }
