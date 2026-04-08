from passlib.context import CryptContext


class PasswordHandler:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        if not isinstance(password, str):
            password = str(password)
        return self.pwd_context.hash(password)


hash_util = PasswordHandler()