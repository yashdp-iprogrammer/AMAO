from datetime import timedelta
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlmodel.ext.asyncio.session import AsyncSession
from src.repositories.auth_repository import AuthRepo
from src.security.dependencies import invalidated_tokens
from src.utils.logger import logger
from src.security.o_auth import auth_dependency
from src.utils.hash_util import hash_util


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.auth_repo = AuthRepo(session)
        self.auth_handler = auth_dependency
        self.hash_handler = hash_util
        self.invalidated_tokens = invalidated_tokens


    # -------------------- LOGIN --------------------
    async def login(self, form_data: OAuth2PasswordRequestForm) -> dict:

        user = await self.auth_repo.get_user_by_email(form_data.username)
        if not user or not self.hash_handler.verify_password(form_data.password, user.user_password):
            logger.warning(f"[LOGIN] Login failed: {form_data.username}")
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        access_token_expires = timedelta(minutes=self.auth_handler.access_token_expiry_time)

        access_token = self.auth_handler.create_access_token(
            data={"sub": str(user.user_id)},
            expires_delta=access_token_expires
        )

        refresh_token_expires = timedelta(days=7)
        refresh_token = self.auth_handler.create_access_token(
            data={"sub": str(user.user_id)},
            expires_delta=refresh_token_expires
        )

        logger.info(f"[LOGIN] Login successful: {form_data.username}")

        return {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }


    # -------------------- REFRESH --------------------
    async def refresh_access_token(self, refresh_token: str) -> dict:
        logger.info("[REFRESH TOKEN] Refreshing access token")

        try:
            payload = self.auth_handler.decode_jwt_token(refresh_token)
            user_id = payload.get("sub")

            if not user_id:
                logger.warning("[REFRESH TOKEN] Invalid refresh token: missing subject")
                raise HTTPException(status_code=401, detail="Invalid refresh token")

            access_token_expires = timedelta(minutes=self.auth_handler.access_token_expiry_time)

            new_access_token = self.auth_handler.create_access_token(
                data={"sub": user_id},
                expires_delta=access_token_expires
            )

            logger.info(f"[REFRESH TOKEN] Access token refreshed for user: {user_id}")

            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }

        except JWTError:
            logger.warning("[REFRESH TOKEN] Invalid or expired refresh token")
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # -------------------- LOGOUT --------------------
    async def logout(self, token: str):
        self.invalidated_tokens.add(token)
        logger.info("[LOGOUT] User logged out (token invalidated)")
        return {"message": "Logged out successfully"}
