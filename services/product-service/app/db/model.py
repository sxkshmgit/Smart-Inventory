"""What we store in MongoDB, one model per collection.

The same models are also what the API returns (used as response_model), so a
field that isn't here can never reach the client.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Generic, TypeVar

from bson import Decimal128, ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _to_str(value):
    """Mongo's ObjectId -> plain string."""
    if isinstance(value, ObjectId):
        return str(value)
    return value


def _to_decimal(value):
    """Mongo's Decimal128 -> Python Decimal."""
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return value


# An id that is an ObjectId in MongoDB but a string in Python and in the API.
PyObjectId = Annotated[str, BeforeValidator(_to_str)]

# Money is a Decimal, not a float: floats round (0.1 + 0.2 = 0.30000000000000004).
Money = Annotated[Decimal, BeforeValidator(_to_decimal), Field(ge=0, decimal_places=2)]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MongoModel(BaseModel):
    """Base class: reads Mongo's `_id` into `id`, and turns the model back into a Mongo dict."""

    # populate_by_name: the model can be filled with "id" as well as "_id".
    # use_enum_values: enums (like status) are stored as plain strings.
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
    """One page of results, e.g. Page[Product]. Used by list endpoints."""

    items: list[T]
    total: int  # matches across all pages
    page: int
    page_size: int
    pages: int


# ---------- Category ----------
class Category(MongoModel):
    name: str
    created_by: str
    created_at: datetime = Field(default_factory=utcnow)

    def to_mongo(self) -> dict:
        data = super().to_mongo()
        # Stored only for the unique index: "Electronics" and "electronics" are the same category.
        data["name_lower"] = self.name.lower()
        return data


# ---------- Product ----------
class ProductStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProductImage(BaseModel):
    """Image metadata only: the file itself lives elsewhere (e.g. a CDN)."""

    url: str = Field(min_length=1, max_length=500)
    alt: str | None = Field(default=None, max_length=200)


class Product(MongoModel):
    sku: str
    name: str
    description: str | None = None
    category_id: PyObjectId  # reference to Category.id
    category_name: str  # copy for display; safe because categories can't be renamed
    brand: str | None = None
    supplier_ids: list[str] = []
    cost_price: Money
    selling_price: Money
    reorder_level: int = 0
    tax_percentage: float = 0
    unit: str = "pcs"
    images: list[ProductImage] = []
    status: ProductStatus = ProductStatus.ACTIVE
    created_by: str
    updated_by: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def to_mongo(self) -> dict:
        data = super().to_mongo()
        # BSON can't store Python Decimal; use Decimal128.
        data["cost_price"] = Decimal128(str(self.cost_price))
        data["selling_price"] = Decimal128(str(self.selling_price))
        data["category_id"] = ObjectId(self.category_id)
        return data
