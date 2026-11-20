"""All MongoDB access for products. No other file talks to the products collection."""

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db


class DuplicateSkuError(Exception):
    """Raised when a product with the same SKU already exists."""


def _products():
    return get_db()["products"]


def _counters():
    # One document per SKU prefix, e.g. {"_id": "ELE", "value": 42}.
    return get_db()["counters"]


async def create_indexes() -> None:
    await _products().create_index("sku", unique=True)
    await _products().create_index("name")
    await _products().create_index("category")


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
