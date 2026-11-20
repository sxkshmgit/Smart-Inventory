"""Business rules for products."""

import math
import re

from fastapi import HTTPException, status

from app.db import product_repository
from app.db.models import new_product_document, product_to_out
from app.schemas.product import ProductCreate


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
