from fastapi.security import OAuth2PasswordBearer

invalidated_tokens = set()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")