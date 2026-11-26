"""/products/categories endpoints: create, list, get and delete. Categories can't be renamed.

Each request model sits right above the route that uses it. Responses are the
Category model from db/model.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.db import db_queries
from app.db.model import Category
from app.routes.deps import require_permission

router = APIRouter(tags=["Categories"])


# ---------- create ----------
class CategoryCreate(BaseModel):
    """Body of POST /products/categories."""

    name: str = Field(min_length=2, max_length=100)


@router.post("", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, user: dict = Depends(require_permission("product:create"))):
    category = Category(name=data.name, created_by=user["id"])
    try:
        return await db_queries.create_category(category)
    except db_queries.DuplicateCategoryError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category '{data.name}' already exists")


# ---------- list ----------
@router.get("", response_model=list[Category], dependencies=[Depends(require_permission("product:read"))])
async def list_categories():
    return await db_queries.list_categories()


# ---------- get ----------
@router.get("/{category_id}", response_model=Category, dependencies=[Depends(require_permission("product:read"))])
async def get_category(category_id: str):
    category = await db_queries.get_category(category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


# ---------- delete ----------
@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("product:delete"))],
)
async def delete_category(category_id: str):
    """Hard delete: the category is removed from the database, but only if no product uses it."""
    if await db_queries.get_category(category_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")

    in_use = await db_queries.count_products_in_category(category_id)
    if in_use:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category is used by {in_use} product(s)")

    if not await db_queries.delete_category(category_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
