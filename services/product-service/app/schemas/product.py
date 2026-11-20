"""Request and response shapes for /products.

FastAPI validates every request body against these classes. Bad input never
reaches our code: the client gets a 422 with the reason.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ProductStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProductImage(BaseModel):
    """Image metadata only: the file itself lives elsewhere (e.g. a CDN)."""

    url: str = Field(min_length=1, max_length=500)
    alt: str | None = Field(default=None, max_length=200)


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(min_length=2, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    supplier_ids: list[str] = []
    cost_price: float = Field(ge=0)
    selling_price: float = Field(ge=0)
    reorder_level: int = Field(default=0, ge=0)
    tax_percentage: float = Field(default=0, ge=0, le=100)
    unit: str = Field(default="pcs", min_length=1, max_length=20)
    images: list[ProductImage] = []

    @model_validator(mode="after")
    def selling_not_below_cost(self):
        if self.selling_price < self.cost_price:
            raise ValueError("selling_price cannot be lower than cost_price")
        return self


class ProductOut(BaseModel):
    """What the API returns for a product."""

    id: str
    sku: str
    name: str
    description: str | None
    category: str
    brand: str | None
    supplier_ids: list[str]
    cost_price: float
    selling_price: float
    reorder_level: int
    tax_percentage: float
    unit: str
    images: list[ProductImage]
    status: ProductStatus
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
