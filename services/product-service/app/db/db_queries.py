"""All MongoDB access for products and categories. No other file talks to the database."""

import re
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db


class DuplicateSkuError(Exception):
    """Raised when a product with the same SKU already exists."""


class DuplicateCategoryError(Exception):
    """Raised when a category with the same name already exists under the same parent."""


def _products():
    return get_db()["products"]


def _counters():
    # One document per SKU prefix, e.g. {"_id": "ELE", "value": 42}.
    return get_db()["counters"]


def _categories():
    return get_db()["categories"]


async def create_indexes() -> None:
    await _products().create_index("sku", unique=True)
    await _products().create_index("name")
    await _products().create_index("category_id")
    # Same name can't appear twice under the same parent (top-level ones have parent_id None).
    await _categories().create_index([("parent_id", 1), ("name_lower", 1)], unique=True)


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


async def create(product_doc: dict) -> dict:
    try:
        result = await _products().insert_one(product_doc)
    except DuplicateKeyError:
        raise DuplicateSkuError(product_doc["sku"])
    return {**product_doc, "_id": result.inserted_id}


def _build_query(search=None, category_ids=None, status=None, supplier_id=None) -> dict:
    """Turn the optional filters into a MongoDB query. Filters that are None are skipped."""
    query = {}
    if search:
        # re.escape: the user's text is matched literally, not as a regex pattern.
        pattern = {"$regex": re.escape(search), "$options": "i"}  # "i" = ignore case
        query["$or"] = [{"name": pattern}, {"sku": pattern}]
    if category_ids:
        query["category_id"] = {"$in": category_ids}  # a category and its subcategories
    if status:
        query["status"] = status
    if supplier_id:
        query["supplier_ids"] = supplier_id  # matches if the list contains this id
    return query


async def list_products(skip: int, limit: int, **filters) -> list[dict]:
    """Newest first. `filters` are the same keywords as _build_query."""
    cursor = _products().find(_build_query(**filters)).sort("created_at", -1).skip(skip).limit(limit)
    return await cursor.to_list()


async def count(**filters) -> int:
    return await _products().count_documents(_build_query(**filters))


def _to_object_id(product_id: str) -> ObjectId | None:
    """Turn a string id into an ObjectId, or None if it isn't a valid id."""
    try:
        return ObjectId(product_id)
    except (InvalidId, TypeError):
        return None


async def get_by_id(product_id: str) -> dict | None:
    oid = _to_object_id(product_id)
    if oid is None:
        return None
    return await _products().find_one({"_id": oid})


async def update(product_id: str, fields: dict) -> dict | None:
    """Set the given fields and updated_at. Return the updated product, or None if not found."""
    oid = _to_object_id(product_id)
    if oid is None:
        return None
    return await _products().find_one_and_update(
        {"_id": oid},
        {"$set": {**fields, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )


# ---------- Categories ----------

async def create_category(category_doc: dict) -> dict:
    try:
        result = await _categories().insert_one(category_doc)
    except DuplicateKeyError:
        raise DuplicateCategoryError(category_doc["name"])
    return {**category_doc, "_id": result.inserted_id}


async def get_category(category_id: str) -> dict | None:
    oid = _to_object_id(category_id)
    if oid is None:
        return None
    return await _categories().find_one({"_id": oid})


async def list_categories(parent_id: str | None) -> list[dict]:
    """parent_id None = main categories; otherwise the subcategories of that parent. A-Z by name."""
    return await _categories().find({"parent_id": parent_id}).sort("name_lower", 1).to_list()


async def update_category(category_id: str, fields: dict) -> dict | None:
    oid = _to_object_id(category_id)
    if oid is None:
        return None
    try:
        return await _categories().find_one_and_update(
            {"_id": oid},
            {"$set": {**fields, "updated_at": datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise DuplicateCategoryError(fields.get("name"))


async def delete_category(category_id: str) -> None:
    await _categories().delete_one({"_id": _to_object_id(category_id)})


async def count_subcategories(category_id: str) -> int:
    return await _categories().count_documents({"parent_id": category_id})


async def subcategory_ids(category_id: str) -> list[str]:
    children = await _categories().find({"parent_id": category_id}, {"_id": 1}).to_list()
    return [str(c["_id"]) for c in children]


async def count_products_in_category(category_id: str) -> int:
    return await _products().count_documents({"category_id": category_id})


async def rename_category_in_products(category_id: str, name: str) -> None:
    """Products keep a copy of the category name, so a rename is copied to them too."""
    await _products().update_many({"category_id": category_id}, {"$set": {"category_name": name}})
