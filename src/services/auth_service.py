# src/services/auth_service.py
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import uuid4
from src.repositories.auth_repository import AuthRepo
from src.Database.models import User
from src.security.dependencies import invalidated_tokens
from src.utils.logger import logger
from src.schema.user_schema import UserCreate
from src.security.o_auth import auth_dependency
from src.utils.hash_util import hash_util



class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.auth_repo = AuthRepo(session)
        self.auth_handler = auth_dependency
        self.hash_handler = hash_util
        self.invalidated_tokens = invalidated_tokens

    # -------------------- REGISTER --------------------
    async def register_user(self, user_data: UserCreate) -> User:
        logger.info(f"Registering user: {user_data.user_name}")

        # Hash password
        hashed_password = self.hash_handler.get_password_hash(user_data.password)

        # Create User instance
        user = User(
            user_id=str(uuid4()),  # generate unique string ID
            user_name=user_data.user_name,
            email_id=user_data.user_email,
            hashed_password=hashed_password,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        # Save to DB
        user = await self.auth_repo.create_user(user)
        logger.info(f"User created successfully: {user.user_id}")
        return user

    # -------------------- LOGIN --------------------
    async def login(self, form_data: OAuth2PasswordRequestForm) -> dict:
        # Fetch user by email
        user = await self.auth_repo.get_user_by_email(form_data.username)
        if not user or not self.hash_handler.verify_password(form_data.password, user.user_password):
            logger.warning(f"❌ Login failed for {form_data.username}")
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        # Generate tokens
        access_token_expires = timedelta(minutes=self.auth_handler.access_token_expiry_time)
        print("user_id", user.user_id)
        access_token = self.auth_handler.create_access_token(
            data={"sub": str(user.user_id)},  # Ensure sub is string
            expires_delta=access_token_expires
        )

        refresh_token_expires = timedelta(days=7)
        refresh_token = self.auth_handler.create_access_token(
            data={"sub": str(user.user_id)},  # Ensure sub is string
            expires_delta=refresh_token_expires
        )

        logger.info(f"✅ Login successful for {form_data.username}")
        return {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }


    # -------------------- REFRESH --------------------
    async def refresh_access_token(self, refresh_token: str) -> dict:
        try:
            payload = self.auth_handler.decode_jwt_token(refresh_token)
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid refresh token")

            access_token_expires = timedelta(minutes=self.auth_handler.access_token_expiry_time)
            new_access_token = self.auth_handler.create_access_token(
                data={"sub": user_id}, expires_delta=access_token_expires
            )
            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # -------------------- LOGOUT --------------------
    async def logout(self, token: str):
        self.invalidated_tokens.add(token)
        logger.info("✅ Token invalidated")
        return {"message": "Logged out successfully"}
