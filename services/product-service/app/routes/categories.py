"""/products/categories endpoints: create, list, get and delete. Categories can't be renamed."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.db import db_queries
from app.db.helpers import category_to_out, new_category_document
from app.db.model import CategoryCreate, CategoryOut
from app.routes.deps import require_permission

router = APIRouter(tags=["Categories"])


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, user: dict = Depends(require_permission("product:create"))):
    category_doc = new_category_document(data.name, created_by=user["id"])
    try:
        category = await db_queries.create_category(category_doc)
    except db_queries.DuplicateCategoryError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category '{data.name}' already exists")
    return category_to_out(category)


@router.get("", response_model=list[CategoryOut], dependencies=[Depends(require_permission("product:read"))])
async def list_categories():
    return [category_to_out(c) for c in await db_queries.list_categories()]


@router.get("/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_permission("product:read"))])
async def get_category(category_id: str):
    category = await db_queries.get_category(category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category_to_out(category)


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
