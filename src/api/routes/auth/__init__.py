from typing import Annotated
from src.Database import system_db as db
from src.utils.logger import logger
from fastapi import APIRouter, Depends, Body
from src.services.auth_service import AuthService
from src.security.dependencies import oauth2_scheme
from sqlmodel.ext.asyncio.session import AsyncSession
from src.schema.user_schema import Login, UserCreate, CurrentUser
from src.security.o_auth import auth_dependency


router = APIRouter(tags=["Auth"])

def get_auth_service(session: AsyncSession = Depends(db.get_session)) -> AuthService:
    return AuthService(session)

auth_session = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/login")
async def login(
    service: auth_session,
    data: Login = Body(...)
):
    logger.info(f"[LOGIN] Attempt user={data.username}")

    class FormData:
        def __init__(self, username, password):
            self.username = username
            self.password = password

    form_data = FormData(data.username, data.password)

    result = await service.login(form_data)

    return result


@router.post("/refresh")
async def refresh_token(
    service: auth_session,
    refresh_token: str = Body(..., embed=True),
):
    logger.info("[REFRESH_TOKEN] Request received")

    result = await service.refresh_access_token(refresh_token)

    return result


@router.delete("/logout")
async def logout(
    service: auth_session,
    token: str = Depends(oauth2_scheme)
):
    logger.info("[LOGOUT] Request received")

    result = await service.logout(token)

    return result


@router.get("/get-current-user", response_model=CurrentUser)
async def get_current_user(
    current_user = Depends(auth_dependency.get_current_active_user)
):
    logger.info(f"[GET_CURRENT_USER] user={current_user}")
    return current_user