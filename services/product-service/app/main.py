"""Application entry point. Run with: uvicorn app.main:app --port 8003"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import close_db, connect_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="Product-service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
