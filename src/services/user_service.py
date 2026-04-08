from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.user_repository import UserRepo
from src.Database.models import User
from src.schema.user_schema import CurrentUser, UserCreate, UserUpdate
from src.utils.hash_util import hash_util
from src.utils.logger import logger


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepo(session)
        self.hash_handler = hash_util

    async def create_user(self, user_data: UserCreate, current_user: CurrentUser):
        logger.info(f"[USER] Creating user: {user_data.user_email}")

        existing = await self.user_repo.get_user_by_email(user_data.user_email)
        if existing:
            logger.warning(f"[USER] User already exists: {user_data.user_email}")
            raise HTTPException(status_code=400, detail="User already exists")

        hashed_password = self.hash_handler.get_password_hash(user_data.user_password)

        user = User(
            user_id=str(uuid4()),
            client_id=user_data.client_id,
            user_name=user_data.user_name,
            user_email=user_data.user_email,
            user_mobile=user_data.user_mobile,
            user_password=hashed_password,
            role_id=user_data.role_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_disabled=False
        )

        created_user = await self.user_repo.create_user(user, current_user)

        logger.info(f"[USER] User created successfully: {user.user_id}")

        return {
            "message": "User created successfully",
            "user": created_user
        }


    async def update_user(self, user_id: str, user: UserUpdate, current_user: CurrentUser):
        logger.info(f"[USER] Updating user: {user_id}")

        existing_user = await self.user_repo.get_user_by_id(user_id, current_user)

        if not existing_user:
            logger.warning(f"[USER] User not found for update: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        updated_user = await self.user_repo.update_user(existing_user, user, current_user)

        logger.info(f"[USER] User updated successfully: {user_id}")

        return {
            "message": "User updated successfully",
            "user": updated_user
        }


    async def delete_user(self, user_id: str, current_user: CurrentUser):
        logger.info(f"[USER] Deleting user: {user_id}")

        existing_user = await self.user_repo.get_user_by_id(user_id, current_user)

        if not existing_user:
            logger.warning(f"[USER] User not found for deletion: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        await self.user_repo.delete_user(existing_user, current_user)

        logger.info(f"[USER] User deleted successfully: {user_id}")

        return {"message": "User deleted successfully"}
    
    
    async def get_all_users(
        self,
        current_user: CurrentUser,
        client_id: Optional[str] = None,
        page: int = 1,
        size: int = 10
    ):
        logger.info(f"[USER] Fetching users | client_id={client_id}, page={page}, size={size}")
        return await self.user_repo.get_all_users(client_id, current_user, page, size)


    async def get_user_by_id(self, user_id: str, current_user: CurrentUser):
        logger.info(f"[USER] Fetching user by id: {user_id}")
        
        user = await self.user_repo.get_user_by_id(user_id, current_user)
        
        if not user:
            logger.warning(f"[USER] User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        return user
