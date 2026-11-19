"""The only code that reads or writes the `users` collection."""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db


class DuplicateEmailError(Exception):
    """Raised when a user with the same email already exists."""


def _users():
    return get_db()["users"]


async def create_indexes() -> None:
    """Called once at startup; existing indexes are kept.

    The unique email index makes the database itself refuse a second user
    with the same email, even if two registrations arrive at the same moment.
    """
    await _users().create_index("email", unique=True)
    await _users().create_index("role")


async def create(user_doc: dict) -> dict:
    """Insert a new user and return it with its new `_id`."""
    try:
        result = await _users().insert_one(user_doc)
    except DuplicateKeyError:
        raise DuplicateEmailError(user_doc["email"])
    return {**user_doc, "_id": result.inserted_id}


async def get_by_email(email: str) -> dict | None:
    return await _users().find_one({"email": email.lower()})


def _to_object_id(user_id: str) -> ObjectId | None:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        return None


async def get_by_id(user_id: str) -> dict | None:
    """Returns None if the id is not a valid ObjectId or no user has it."""
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None
    return await _users().find_one({"_id": object_id})


async def list_users(role: str | None, skip: int, limit: int) -> list[dict]:
    """One page of users, newest first, optionally only one role."""
    query = {"role": role} if role else {}
    cursor = _users().find(query).sort("created_at", -1).skip(skip).limit(limit)
    return await cursor.to_list()


async def count(role: str | None) -> int:
    query = {"role": role} if role else {}
    return await _users().count_documents(query)


async def update(user_id: str, fields: dict) -> dict | None:
    """Set the given fields plus updated_at; return the updated user, or None if not found."""
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None
    changes = {**fields, "updated_at": datetime.now(timezone.utc)}
    return await _users().find_one_and_update(
        {"_id": object_id},
        {"$set": changes},
        return_document=ReturnDocument.AFTER,
    )
