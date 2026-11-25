"""/products/categories endpoints and their business rules.

Two levels only: main categories (Electronics) and their subcategories (Mobiles).
Uses the product permissions, so no extra permissions are needed in auth-service.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.db import db_queries
from app.db.helpers import category_to_out, new_category_document
from app.db.model import CategoryCreate, CategoryOut, CategoryUpdate
from app.routes.deps import require_permission

router = APIRouter(tags=["Categories"])


async def _get_or_404(category_id: str) -> dict:
    category = await db_queries.get_category(category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, user: dict = Depends(require_permission("product:create"))):
    if data.parent_id is not None:
        parent = await db_queries.get_category(data.parent_id)
        if parent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Parent category not found")
        if parent["parent_id"] is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A subcategory can't have its own subcategories")

    category_doc = new_category_document(data.name, data.parent_id, created_by=user["id"])
    try:
        category = await db_queries.create_category(category_doc)
    except db_queries.DuplicateCategoryError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category '{data.name}' already exists here")
    return category_to_out(category)


@router.get("", response_model=list[CategoryOut], dependencies=[Depends(require_permission("product:read"))])
async def list_categories(parent_id: str | None = None):
    """Without parent_id: the main categories. With parent_id: that category's subcategories."""
    return [category_to_out(c) for c in await db_queries.list_categories(parent_id)]


@router.get("/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_permission("product:read"))])
async def get_category(category_id: str):
    return category_to_out(await _get_or_404(category_id))


@router.patch("/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_permission("product:update"))])
async def rename_category(category_id: str, data: CategoryUpdate):
    await _get_or_404(category_id)
    try:
        category = await db_queries.update_category(
            category_id, {"name": data.name, "name_lower": data.name.lower()}
        )
    except db_queries.DuplicateCategoryError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category '{data.name}' already exists here")
    await db_queries.rename_category_in_products(category_id, data.name)
    return category_to_out(category)


@router.delete(
    "/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("product:delete"))]
)
async def delete_category(category_id: str):
    """Removed for real (categories have no history to keep), but only when nothing depends on them."""
    await _get_or_404(category_id)
    if await db_queries.count_subcategories(category_id) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Delete its subcategories first")
    used_by = await db_queries.count_products_in_category(category_id)
    if used_by > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category is used by {used_by} product(s)")
    await db_queries.delete_category(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
