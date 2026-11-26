"""The only code that reads or writes the `users` collection.

Functions take and return the User model from db/model.py, never raw Mongo dicts.
"""

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db
from app.db.model import User, utcnow


class DuplicateEmailError(Exception):
    """Raised when a user with the same email already exists."""


def _users():
    return get_db()["users"]


def _to_object_id(user_id: str) -> ObjectId | None:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        return None


async def create_indexes() -> None:
    """Called once at startup; existing indexes are kept.

    The unique email index makes the database itself refuse a second user
    with the same email, even if two registrations arrive at the same moment.
    """
    await _users().create_index("email", unique=True)
    await _users().create_index("role")


async def create(user: User) -> User:
    """Insert a new user and return it with its new id."""
    try:
        result = await _users().insert_one(user.to_mongo())
    except DuplicateKeyError:
        raise DuplicateEmailError(user.email)
    return user.model_copy(update={"id": str(result.inserted_id)})


async def get_by_email(email: str) -> User | None:
    doc = await _users().find_one({"email": email.lower()})
    return User.model_validate(doc) if doc else None


async def get_by_id(user_id: str) -> User | None:
    """Returns None if the id is not a valid ObjectId or no user has it."""
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None
    doc = await _users().find_one({"_id": object_id})
    return User.model_validate(doc) if doc else None


async def list_users(role: str | None, skip: int, limit: int) -> list[User]:
    """One page of users, newest first, optionally only one role."""
    query = {"role": role} if role else {}
    cursor = _users().find(query).sort("created_at", -1).skip(skip).limit(limit)
    return [User.model_validate(doc) for doc in await cursor.to_list()]


async def count(role: str | None) -> int:
    query = {"role": role} if role else {}
    return await _users().count_documents(query)


async def update(user: User) -> User | None:
    """Save the changed user (with a new updated_at). Return it, or None if not found."""
    data = user.to_mongo()
    data.pop("_id")  # the id itself never changes
    data["updated_at"] = utcnow()
    doc = await _users().find_one_and_update(
        {"_id": ObjectId(user.id)},
        {"$set": data},
        return_document=ReturnDocument.AFTER,
    )
    return User.model_validate(doc) if doc else None
