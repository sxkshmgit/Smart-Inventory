"""/products endpoints and their business rules.

Every route is protected by a permission carried in the token.
"""

import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import db_queries
from app.db.helpers import new_product_document, product_to_out
from app.db.model import ProductCreate, ProductList, ProductOut, ProductStatus, ProductUpdate
from app.routes.deps import require_permission

router = APIRouter(tags=["Products"])


async def _get_or_404(product_id: str) -> dict:
    product = await db_queries.get_by_id(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


def _sku_prefix(category: str) -> str:
    """First 3 letters of the category in capitals: "Electronics" -> "ELE"."""
    letters = re.sub(r"[^A-Za-z]", "", category)
    return letters[:3].upper() or "PRD"


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, user: dict = Depends(require_permission("product:create"))):
    prefix = _sku_prefix(data.category)
    number = await db_queries.next_sequence(prefix)
    sku = f"{prefix}-{number:06d}"  # e.g. ELE-000001

    product_doc = new_product_document(data.model_dump(), sku=sku, created_by=user["id"])
    try:
        product = await db_queries.create(product_doc)
    except db_queries.DuplicateSkuError:
        # Only possible if the counter was reset by hand.
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU {sku} already exists, try again")
    return product_to_out(product)


@router.get("", response_model=ProductList, dependencies=[Depends(require_permission("product:read"))])
async def list_products(
    search: str | None = Query(None, max_length=100, description="Part of the name or SKU"),
    category: str | None = None,
    status: ProductStatus | None = None,
    supplier_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    filters = {"search": search, "category": category, "status": status, "supplier_id": supplier_id}
    skip = (page - 1) * page_size
    products = await db_queries.list_products(skip=skip, limit=page_size, **filters)
    total = await db_queries.count(**filters)
    return {
        "items": [product_to_out(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


@router.get("/{product_id}", response_model=ProductOut, dependencies=[Depends(require_permission("product:read"))])
async def get_product(product_id: str):
    return product_to_out(await _get_or_404(product_id))


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str, data: ProductUpdate, user: dict = Depends(require_permission("product:update"))
):
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

    product = await db_queries.update(product_id, {**fields, "updated_by": user["id"]})
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product_to_out(product)


@router.delete("/{product_id}", response_model=ProductOut)
async def delete_product(product_id: str, user: dict = Depends(require_permission("product:delete"))):
    """Soft delete: the product is marked inactive but stays in the database."""
    await _get_or_404(product_id)
    product = await db_queries.update(product_id, {"status": "inactive", "updated_by": user["id"]})
    return product_to_out(product)
