"""What we store in MongoDB, one model per collection.

The same models are also what the API returns (used as response_model), so a
field that isn't here, or is marked exclude=True, can never reach the client.
"""

from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, field_validator

from app.core.permissions import Role


def _to_str(value):
    """Mongo's ObjectId -> plain string."""
    if isinstance(value, ObjectId):
        return str(value)
    return value


# An id that is an ObjectId in MongoDB but a string in Python and in the API.
PyObjectId = Annotated[str, BeforeValidator(_to_str)]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MongoModel(BaseModel):
    """Base class: reads Mongo's `_id` into `id`, and turns the model back into a Mongo dict."""

    # populate_by_name: the model can be filled with "id" as well as "_id".
    # use_enum_values: enums (like role) are stored as plain strings.
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    # validation_alias: read from "_id" in MongoDB, but shown as "id" in the API.
    id: PyObjectId | None = Field(default=None, validation_alias="_id")

    def to_mongo(self) -> dict:
        """Dict ready for insert_one(). Without an id, MongoDB generates one."""
        data = self.model_dump(exclude={"id"})
        if self.id is not None:
            data["_id"] = ObjectId(self.id)
        return data


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """One page of results, e.g. Page[User]. Used by list endpoints."""

    items: list[T]
    total: int  # matches across all pages
    page: int
    page_size: int
    pages: int


# ---------- User ----------
class User(MongoModel):
    email: EmailStr
    # exclude=True: never part of model_dump(), so never in any API response.
    # to_mongo() adds it back when saving.
    hashed_password: str = Field(exclude=True)
    full_name: str
    role: Role = Role.VIEWER
    warehouse_ids: list[str] = []
    is_active: bool = True
    created_by: str | None = None  # admin's id, or None if self-registered
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        # "A@x.com" and "a@x.com" are the same user.
        return value.lower()

    def to_mongo(self) -> dict:
        data = super().to_mongo()
        data["hashed_password"] = self.hashed_password
        return data
