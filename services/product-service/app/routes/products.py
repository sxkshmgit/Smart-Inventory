"""/products endpoints. Every route is protected by a permission carried in the token."""

from fastapi import APIRouter, Depends, status

from app.routes.deps import require_permission
from app.schemas.product import ProductCreate, ProductOut
from app.services import product_service

router = APIRouter(tags=["Products"])


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, user: dict = Depends(require_permission("product:create"))):
    return await product_service.create_product(data, user)
