"""/products endpoints and their business rules.

Every route is protected by a permission carried in the token.
Each request model sits right above the route that uses it. Responses are the
Product model from db/model.py.
"""

import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db import db_queries
from app.db.model import Category, Money, Page, Product, ProductImage, ProductStatus
from app.routes.deps import require_permission

router = APIRouter(tags=["Products"])


async def _get_or_404(product_id: str) -> Product:
    product = await db_queries.get_by_id(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


async def _get_category_or_400(category_id: str) -> Category:
    """The category a product points to must exist."""
    category = await db_queries.get_category(category_id)
    if category is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Category not found")
    return category


def _sku_prefix(category_name: str) -> str:
    """First 3 letters of the category name in capitals: "Electronics" -> "ELE"."""
    letters = re.sub(r"[^A-Za-z]", "", category_name)
    return letters[:3].upper() or "PRD"


# ---------- create ----------
class ProductCreate(BaseModel):
    """Body of POST /products. sku, status and created_by are set by the server."""

    # Trim spaces around text fields before validating them.
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category_id: str = Field(min_length=1, description="Id from GET /products/categories")
    brand: str | None = Field(default=None, max_length=100)
    supplier_ids: list[str] = []
    cost_price: Money
    selling_price: Money
    reorder_level: int = Field(default=0, ge=0)
    tax_percentage: float = Field(default=0, ge=0, le=100)
    unit: str = Field(default="pcs", min_length=1, max_length=20)
    images: list[ProductImage] = []

    @model_validator(mode="after")
    def selling_not_below_cost(self):
        if self.selling_price < self.cost_price:
            raise ValueError("selling_price cannot be lower than cost_price")
        return self


@router.post("", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, user: dict = Depends(require_permission("product:create"))):
    category = await _get_category_or_400(data.category_id)

    prefix = _sku_prefix(category.name)
    number = await db_queries.next_sequence(prefix)
    sku = f"{prefix}-{number:06d}"  # e.g. ELE-000001

    product = Product(
        **data.model_dump(),
        sku=sku,
        # Copy of the category name so product lists don't need a second lookup.
        category_name=category.name,
        created_by=user["id"],
        updated_by=user["id"],
    )
    try:
        return await db_queries.create(product)
    except db_queries.DuplicateSkuError:
        # Only possible if the counter was reset by hand.
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU {sku} already exists, try again")


# ---------- list ----------
@router.get("", response_model=Page[Product], dependencies=[Depends(require_permission("product:read"))])
async def list_products(
    search: str | None = Query(None, max_length=100, description="Part of the name or SKU"),
    category_id: str | None = None,
    status: ProductStatus | None = None,
    supplier_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    filters = {"search": search, "category_id": category_id, "status": status, "supplier_id": supplier_id}
    skip = (page - 1) * page_size
    products = await db_queries.list_products(skip=skip, limit=page_size, **filters)
    total = await db_queries.count(**filters)
    return {
        "items": products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


# ---------- get ----------
@router.get("/{product_id}", response_model=Product, dependencies=[Depends(require_permission("product:read"))])
async def get_product(product_id: str):
    return await _get_or_404(product_id)


# ---------- update ----------
class ProductUpdate(BaseModel):
    """Body of PATCH /products/{id}. Every field is optional: only the fields sent are changed.

    sku, status and created_by can't be changed here.
    """

    # Trim spaces around text fields before validating them.
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category_id: str | None = Field(default=None, min_length=1)
    brand: str | None = Field(default=None, max_length=100)
    supplier_ids: list[str] | None = None
    cost_price: Money | None = None
    selling_price: Money | None = None
    reorder_level: int | None = Field(default=None, ge=0)
    tax_percentage: float | None = Field(default=None, ge=0, le=100)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    images: list[ProductImage] | None = None


@router.patch("/{product_id}", response_model=Product)
async def update_product(
    product_id: str, data: ProductUpdate, user: dict = Depends(require_permission("product:update"))
):
    # Only the fields the client actually sent.
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")

    # Prices are checked against the stored values for anything not sent.
    current = await _get_or_404(product_id)
    cost = fields.get("cost_price", current.cost_price)
    selling = fields.get("selling_price", current.selling_price)
    if selling < cost:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "selling_price cannot be lower than cost_price")

    # Moving to another category: it must exist. The SKU stays the same.
    if "category_id" in fields:
        category = await _get_category_or_400(fields["category_id"])
        fields["category_name"] = category.name

    # Current product + the changes, validated again as a Product.
    updated = Product.model_validate({**current.model_dump(), **fields, "updated_by": user["id"]})
    product = await db_queries.update(updated)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


# ---------- delete ----------
@router.delete("/{product_id}", response_model=Product)
async def delete_product(product_id: str, user: dict = Depends(require_permission("product:delete"))):
    """Soft delete: the product is marked inactive but stays in the database."""
    current = await _get_or_404(product_id)
    updated = current.model_copy(update={"status": ProductStatus.INACTIVE, "updated_by": user["id"]})
    product = await db_queries.update(updated)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product
