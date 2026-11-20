"""/products endpoints. Every route is protected by a permission carried in the token."""

from fastapi import APIRouter, Depends, Query, status

from app.routes.deps import require_permission
from app.schemas.product import ProductCreate, ProductList, ProductOut, ProductStatus
from app.services import product_service

router = APIRouter(tags=["Products"])


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, user: dict = Depends(require_permission("product:create"))):
    return await product_service.create_product(data, user)


@router.get("", response_model=ProductList, dependencies=[Depends(require_permission("product:read"))])
async def list_products(
    search: str | None = Query(None, max_length=100, description="Part of the name or SKU"),
    category: str | None = None,
    status: ProductStatus | None = None,
    supplier_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await product_service.list_products(
        page, page_size, search=search, category=category, status=status, supplier_id=supplier_id
    )
