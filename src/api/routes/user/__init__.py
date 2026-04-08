from fastapi import APIRouter, Depends, Query
from typing import Annotated, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.schema.user_schema import CurrentUser, UserCreate, UserResponseList, UserUpdate, UserRead, UserResponse
from src.services.user_service import UserService
from src.Database import system_db as db
from src.security.o_auth import auth_dependency
from src.utils.logger import logger

router = APIRouter(prefix="/users", tags=["Users"])


def get_user_service(session: AsyncSession = Depends(db.get_session)) -> UserService:
    return UserService(session)

user_session = Annotated[UserService, Depends(get_user_service)]


@router.post("/add-user", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    service: user_session,
    current_user: CurrentUser = Depends(auth_dependency.require_roles(["SuperAdmin", "Admin"]))
):
    logger.info(f"[CREATE_USER] user_id={current_user.user_id}, target_user_email={user.user_email}") 
    return await service.create_user(user, current_user)


@router.put("/update-user/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user: UserUpdate,
    service: user_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin"]))
):
    logger.info(f"[UPDATE_USER] user_id={current_user.user_id}, target_user_id={user_id}")
    return await service.update_user(user_id, user, current_user)


@router.delete("/remove-user/{user_id}")
async def delete_user(
    user_id: str,
    service: user_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin"]))
):
    logger.info(f"[UPDATE_USER] user_id={current_user.user_id}, target_user_id={user_id}")
    return await service.delete_user(user_id, current_user)


@router.get("/list-users", response_model=UserResponseList)
async def get_all_users(
    service: user_session,
    client_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    current_user: CurrentUser = Depends(
        auth_dependency.require_roles(["SuperAdmin", "Admin"])
    )
):
    if client_id:
        logger.info(f"[LIST_USERS] user_id={current_user.user_id}, client_id={client_id}, page={page}, size={size}")
    else:
        logger.info(f"[LIST_USERS] user_id={current_user.user_id}, all_clients, page={page}, size={size}")
    return await service.get_all_users(current_user, client_id, page, size)


@router.get("/get-user/{user_id}", response_model=UserRead)
async def get_user_by_id(
    user_id: str,
    service: user_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin"]))
):
    logger.info(f"[GET_USER] user_id={current_user.user_id}, target_user_id={user_id}")
    return await service.get_user_by_id(user_id, current_user)
