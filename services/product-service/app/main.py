"""Application entry point. Run with: uvicorn app.main:app --port 8003"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import close_db, connect_db
from app.db import db_queries
from app.routes import categories, products


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await db_queries.create_indexes()
    yield
    await close_db()


app = FastAPI(
    title="Product-service",
    version="0.1.0",
    lifespan=lifespan,
)

# Categories first: otherwise "/products/categories" would match "/products/{product_id}".
app.include_router(categories.router, prefix="/products/categories")
app.include_router(products.router, prefix="/products")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
