from typing import Annotated
from src.Database.base_db import Database
from src.utils.logger import logger
from fastapi import APIRouter, Depends, Body
from src.services.auth_service import AuthService
from src.security.dependencies import oauth2_scheme
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm
from src.schema.user_schema import Login, UserCreate, CurrentUser
from src.Database import system_db as db
from src.security.o_auth import auth_dependency



router = APIRouter(tags=["Auth"])

# Dependency injection
def get_auth_service(session: AsyncSession = Depends(db.get_session)) -> AuthService:
    return AuthService(session)

auth_session = Annotated[AuthService, Depends(get_auth_service)]

# -------------------- ROUTES --------------------
@router.post("/register-user")
async def register_user(user: UserCreate, session: auth_session):
    logger.info(f"Registering super admin: {user.user_name}")
    try:
        await session.register_user(user)
        logger.info(f"Super admin user registered successfully: {user.user_name}")
        return {"status": "success", "message": "User Added Successfully"}
    except Exception as e:
        logger.error(f"Error registering super admin {user.user_name}: {e}", exc_info=True)
        raise

@router.post("/login")
async def login(
    service: auth_session,
    data: Login = Body(...)
    # form_data: OAuth2PasswordRequestForm = Depends()

):
    # Convert to a simple object to mimic OAuth2PasswordRequestForm
    class FormData:
        def __init__(self, username, password):
            self.username = username
            self.password = password

    form_data = FormData(data.username, data.password)
    return await service.login(form_data)

@router.post("/refresh")
async def refresh_token(
    service: auth_session,
    refresh_token: str = Body(..., embed=True), 
):
    return await service.refresh_access_token(refresh_token)

@router.delete("/logout")
async def logout(
    service: auth_session,
    token: str = Depends(oauth2_scheme)
):
    return await service.logout(token)


@router.get("/get-current-user", response_model=CurrentUser)
async def get_current_user(
    current_user = Depends(auth_dependency.get_current_active_user)
):
    return current_user