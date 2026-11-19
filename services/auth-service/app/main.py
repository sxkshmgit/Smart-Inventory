"""Application entry point. Run with: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import close_db, connect_db
from app.db import user_repository
from app.routes import auth, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await user_repository.create_indexes()
    yield
    await close_db()


app = FastAPI(
    title="Auth-service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/auth")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
