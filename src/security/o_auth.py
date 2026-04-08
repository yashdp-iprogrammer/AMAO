from fastapi import Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from jose import jwt
from jose.exceptions import JWTError

from src.Database.models import User, Role
from src.security.dependencies import oauth2_scheme, invalidated_tokens
from src.settings.config import config
from src.utils.logger import logger
from src.schema.user_schema import CurrentUser
from src.Database import system_db as db


class AuthDependency:

    def __init__(
        self,
        secret_key: str = config.HASH_SECRET_KEY,
        algorithm: str = config.HASH_ALGORITHM,
        access_token_expiry_time: int = config.TOKEN_EXPIRY_TIME,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expiry_time = int(access_token_expiry_time)

    # ==========================
    # TOKEN CREATION
    # ==========================

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=self.access_token_expiry_time)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def decode_jwt_token(self, token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except JWTError:
            return None

    # ==========================
    # CURRENT USER (JWT → DB)
    # ==========================

    async def get_current_active_user(
        self,
        token: str = Depends(oauth2_scheme),
        session: AsyncSession = Depends(db.get_session),
    ) -> CurrentUser:

        if token in invalidated_tokens:
            logger.warning("Invalidated token used")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalidated",
            )

        payload = self.decode_jwt_token(token)

        if not payload or "sub" not in payload:
            logger.warning("Invalid or malformed JWT token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        user_id = payload["sub"]

        statement = select(User).where(User.user_id == user_id)
        result = await session.exec(statement)
        user = result.first()

        if not user:
            logger.warning(f"User not found for token | user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        role_stmt = select(Role).where(Role.role_id == user.role_id)
        role_result = await session.exec(role_stmt)
        role = role_result.first()

        if not role:
            logger.warning(f"Role not found | user_id={user_id}, role_id={user.role_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role not found",
            )

        return CurrentUser(
            user_id=user.user_id,
            user_name=user.user_name,
            user_email=user.user_email,
            client_id=user.client_id,
            role_id=user.role_id,
            role_name=role.role_name,
        )

    # ==========================
    # ROLE CHECK
    # ==========================

    def require_roles(self, allowed_roles: List[str]):

        async def role_checker(
            current_user: CurrentUser = Depends(self.get_current_active_user),
        ):

            if current_user.role_name not in allowed_roles:
                logger.warning(
                    f"Unauthorized role access | user_id={current_user.user_id}, role={current_user.role_name}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Operation not permitted for your role",
                )

            return current_user

        return role_checker


auth_dependency = AuthDependency()