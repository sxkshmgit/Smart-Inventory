"""/auth endpoints: register, login, refresh, me."""

from fastapi import APIRouter, Depends, status

from app.db.models import user_to_out
from app.routes.deps import get_current_user
from app.schemas.user import LoginRequest, RefreshRequest, TokenPair, UserOut, UserRegister
from app.services import auth_service

router = APIRouter(tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister):
    return await auth_service.register(data)


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest):
    return await auth_service.login(data)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest):
    return await auth_service.refresh(data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return user_to_out(user)
