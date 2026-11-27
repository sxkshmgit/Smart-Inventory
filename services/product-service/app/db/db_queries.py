"""All MongoDB access for products and categories. No other file talks to these collections.

Functions take and return the models from db/model.py, never raw Mongo dicts.
"""

import re

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db
from app.db.model import Category, Product, utcnow


class DuplicateSkuError(Exception):
    """Raised when a product with the same SKU already exists."""


class DuplicateCategoryError(Exception):
    """Raised when a category with the same name (any case) already exists."""


def _products():
    return get_db()["products"]


def _counters():
    # One document per SKU prefix, e.g. {"_id": "ELE", "value": 42}.
    return get_db()["counters"]


def _categories():
    return get_db()["categories"]


def _to_object_id(value: str) -> ObjectId | None:
    """Turn a string id into an ObjectId, or None if it isn't a valid id."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def create_indexes() -> None:
    await _products().create_index("sku", unique=True)
    await _products().create_index("name")
    await _products().create_index("category_id")
    await _categories().create_index("name_lower", unique=True)


# ---------- products ----------


async def next_sequence(prefix: str) -> int:
    """Return the next number for this prefix: 1, 2, 3...

    $inc is atomic, so two requests at the same moment never get the same number.
    upsert=True creates the counter the first time a prefix is used.
    """
    counter = await _counters().find_one_and_update(
        {"_id": prefix},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return counter["value"]


async def create(product: Product) -> Product:
    """Insert the product and return it with its new id."""
    try:
        result = await _products().insert_one(product.to_mongo())
    except DuplicateKeyError:
        raise DuplicateSkuError(product.sku)
    return product.model_copy(update={"id": str(result.inserted_id)})


def _build_query(search=None, category_id=None, status=None, supplier_id=None) -> dict:
    """Turn the optional filters into a MongoDB query. Filters that are None are skipped."""
    query = {}
    if search:
        # re.escape: the user's text is matched literally, not as a regex pattern.
        pattern = {"$regex": re.escape(search), "$options": "i"}  # "i" = ignore case
        query["$or"] = [{"name": pattern}, {"sku": pattern}]
    if category_id:
        # Stored as an ObjectId. An invalid id stays a string and matches nothing.
        query["category_id"] = _to_object_id(category_id) or category_id
    if status:
        query["status"] = status
    if supplier_id:
        query["supplier_ids"] = supplier_id  # matches if the list contains this id
    return query


async def list_products(skip: int, limit: int, **filters) -> list[Product]:
    """Newest first. `filters` are the same keywords as _build_query."""
    cursor = _products().find(_build_query(**filters)).sort("created_at", -1).skip(skip).limit(limit)
    return [Product.model_validate(doc) for doc in await cursor.to_list()]


async def count(**filters) -> int:
    return await _products().count_documents(_build_query(**filters))


async def get_by_id(product_id: str) -> Product | None:
    oid = _to_object_id(product_id)
    if oid is None:
        return None
    doc = await _products().find_one({"_id": oid})
    return Product.model_validate(doc) if doc else None


async def get_product_by_name(name: str) -> Product | None:
    """Exact name match. Used by the seed script to skip products that already exist."""
    doc = await _products().find_one({"name": name})
    return Product.model_validate(doc) if doc else None


async def update(product: Product) -> Product | None:
    """Save the changed product (with a new updated_at). Return it, or None if not found."""
    data = product.to_mongo()
    data.pop("_id")  # the id itself never changes
    data["updated_at"] = utcnow()
    doc = await _products().find_one_and_update(
        {"_id": ObjectId(product.id)},
        {"$set": data},
        return_document=ReturnDocument.AFTER,
    )
    return Product.model_validate(doc) if doc else None


# ---------- categories ----------


async def create_category(category: Category) -> Category:
    try:
        result = await _categories().insert_one(category.to_mongo())
    except DuplicateKeyError:
        raise DuplicateCategoryError(category.name)
    return category.model_copy(update={"id": str(result.inserted_id)})


async def list_categories() -> list[Category]:
    """All categories, A to Z."""
    docs = await _categories().find().sort("name_lower", 1).to_list()
    return [Category.model_validate(doc) for doc in docs]


async def get_category(category_id: str) -> Category | None:
    oid = _to_object_id(category_id)
    if oid is None:
        return None
    doc = await _categories().find_one({"_id": oid})
    return Category.model_validate(doc) if doc else None


async def get_category_by_name(name: str) -> Category | None:
    """Name match in any case ("electronics" finds "Electronics")."""
    doc = await _categories().find_one({"name_lower": name.lower()})
    return Category.model_validate(doc) if doc else None


async def count_products_in_category(category_id: str) -> int:
    """How many products point to this category, inactive ones included."""
    return await _products().count_documents({"category_id": _to_object_id(category_id)})


async def delete_category(category_id: str) -> bool:
    """Remove the category for good. Return True if something was deleted."""
    oid = _to_object_id(category_id)
    if oid is None:
        return False
    result = await _categories().delete_one({"_id": oid})
    return result.deleted_count == 1
