"""Business rules for products."""

import math
import re

from fastapi import HTTPException, status

from app.db import product_repository
from app.db.models import new_product_document, product_to_out
from app.schemas.product import ProductCreate, ProductUpdate


async def _get_or_404(product_id: str) -> dict:
    product = await product_repository.get_by_id(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


def _sku_prefix(category: str) -> str:
    """First 3 letters of the category in capitals: "Electronics" -> "ELE"."""
    letters = re.sub(r"[^A-Za-z]", "", category)
    return letters[:3].upper() or "PRD"


async def create_product(data: ProductCreate, user: dict) -> dict:
    prefix = _sku_prefix(data.category)
    number = await product_repository.next_sequence(prefix)
    sku = f"{prefix}-{number:06d}"  # e.g. ELE-000001

    product_doc = new_product_document(data.model_dump(), sku=sku, created_by=user["id"])
    try:
        product = await product_repository.create(product_doc)
    except product_repository.DuplicateSkuError:
        # Only possible if the counter was reset by hand.
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU {sku} already exists, try again")
    return product_to_out(product)


async def list_products(page: int, page_size: int, **filters) -> dict:
    skip = (page - 1) * page_size
    products = await product_repository.list_products(skip=skip, limit=page_size, **filters)
    total = await product_repository.count(**filters)
    return {
        "items": [product_to_out(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


async def get_product(product_id: str) -> dict:
    return product_to_out(await _get_or_404(product_id))


async def update_product(product_id: str, data: ProductUpdate, user: dict) -> dict:
    # Only the fields the client actually sent.
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")

    # Prices are checked against the stored values for anything not sent.
    current = await _get_or_404(product_id)
    cost = fields.get("cost_price", current["cost_price"])
    selling = fields.get("selling_price", current["selling_price"])
    if selling < cost:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "selling_price cannot be lower than cost_price")

    product = await product_repository.update(product_id, {**fields, "updated_by": user["id"]})
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product_to_out(product)


async def deactivate_product(product_id: str, user: dict) -> dict:
    """Soft delete: the product is marked inactive but stays in the database."""
    await _get_or_404(product_id)
    product = await product_repository.update(product_id, {"status": "inactive", "updated_by": user["id"]})
    return product_to_out(product)
