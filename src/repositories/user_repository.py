from fastapi import HTTPException
from datetime import datetime, timezone
from typing import Optional
from src.utils.hash_util import PasswordHandler
from src.utils.logger import logger
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from src.schema.user_schema import CurrentUser, UserUpdate
from src.Database.models import User
from src.utils.hash_util import hash_util


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session
        # self.hash_handler = PasswordHandler()
        self.hash_handler = hash_util

    async def create_user(self, user: User, current_user: CurrentUser):

        if current_user.role_name == "SuperAdmin":
            pass

        elif current_user.role_name == "Admin":
            if user.client_id != current_user.client_id:
                raise HTTPException(
                    status_code=403,
                    detail="Admin can only create users within their own client"
                )

        else:
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to create users"
            )

        try:
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        except Exception as e:
            logger.exception(f"Failed to create user: {e}")
            raise HTTPException(status_code=500, detail="Failed to create user")

        return user
    
    
    async def update_user(self, existing_user: User, user: UserUpdate, current_user: CurrentUser):
        
        if current_user.role_name == "SuperAdmin":
            pass
        elif current_user.role_name == "Admin":
            if existing_user.client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="Admin can only update users within their own client")
        else:
            raise HTTPException(status_code=403, detail="You are not allowed to update user details")

        update_data = user.model_dump(exclude_unset=True)

        password = update_data.pop("user_password", None)
        if password:
            existing_user.user_password = self.hash_handler.get_password_hash(password)

        for key, value in update_data.items():
            setattr(existing_user, key, value)

        existing_user.updated_at = datetime.now(timezone.utc)
        
        self.session.add(existing_user)
        await self.session.commit()
        await self.session.refresh(existing_user)
        return existing_user


    async def delete_user(self, existing_user: User, current_user: CurrentUser):
        
        if current_user.role_name == "SuperAdmin":
            pass
        elif current_user.role_name == "Admin":
            if existing_user.client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="Admin can only delete users within their own client")
        else:
            raise HTTPException(status_code=403, detail="You are not allowed to delete users")

        existing_user.is_disabled = True
        existing_user.updated_at = datetime.now(timezone.utc)

        self.session.add(existing_user)
        await self.session.commit()
    
  
    async def get_all_users(self, client_id: Optional[str], current_user: CurrentUser, page: int, size: int):
        
        statement = select(User).where(User.is_disabled == False)

        if current_user.role_name == "SuperAdmin":
            if client_id:
                statement = statement.where(User.client_id == client_id, User.is_disabled == False)

        elif current_user.role_name == "Admin":
            if client_id and client_id != current_user.client_id:
                raise HTTPException(
                    status_code=403,
                    detail="Admin can only access users within their own client"
                )
            statement = statement.where(User.client_id == current_user.client_id, User.is_disabled == False)

        else:
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to access user details"
            )

        count_stmt = select(func.count()).select_from(statement.subquery())
        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        offset = (page - 1) * size
        statement = statement.offset(offset).limit(size)

        result = await self.session.exec(statement)
        users = result.all()

        total_pages = (total + size - 1) // size

        return {
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "data": users
        }
    

    async def get_user_by_id(self, user_id: str, current_user: CurrentUser):

        statement = select(User).where(
            User.user_id == user_id,
            User.is_disabled == False
        )
        result = await self.session.exec(statement)
        user = result.one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if current_user.role_name == "SuperAdmin":
            return user

        elif current_user.role_name == "Admin":
            if current_user.client_id != user.client_id:
                raise HTTPException(
                    status_code=403,
                    detail="Admin can only access users within their own client"
                )
            return user

        else:
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to access user details"
            )


    async def get_user_by_email(self, email: str):
        statement = select(User).where(
            User.user_email == email,
            User.is_disabled == False
        )
        result = await self.session.exec(statement)
        return result.one_or_none()
