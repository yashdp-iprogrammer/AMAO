# src/utils/hash_util.py
from passlib.context import CryptContext
from src.utils.logger import logger

class PasswordHandler:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        logger.info("PasswordHandler initialized with Argon2 scheme")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            result = self.pwd_context.verify(plain_password, hashed_password)
            logger.debug("Password verification succeeded")
            return result
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False

    def get_password_hash(self, password: str) -> str:
        if not isinstance(password, str):
            password = str(password)
        hashed = self.pwd_context.hash(password)
        logger.debug("Password hashed successfully")
        return hashed

hash_util = PasswordHandler()