from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.Database.models import User
from src.utils.logger import logger

class AuthRepo:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_user(self, user: User) -> User:
        logger.info(f"Adding user with user_id={user.user_id}")
        try:
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            logger.info("User added successfully")
            return user
        except Exception as e:
            logger.exception(f"Failed to add user: {e}")
            raise

    async def get_user_by_email(self, email: str) -> User | None:
        logger.info(f"In Auth Repository checking user for email {email}")
        try:
            statement = select(User).where(User.user_email == email, User.is_disabled == False)

            result = await self.session.exec(statement)
            user = result.one_or_none()

            if user:
                logger.info(f"User found for email: {email}")
            else:
                logger.warning(f"No user found for email: {email}")

            return user

        except Exception as e:
            logger.exception(f"Failed to check user: {e}")
            return None
