import dotenv
import os
from src.utils.logger import logger
dotenv.load_dotenv()


class Config:
    DATABASE_URL = f"mysql+aiomysql://{os.getenv('MY_SQL_USER')}:{os.getenv('MY_SQL_PASSWORD')}@{os.getenv('MY_SQL_HOST')}:{os.getenv('MY_SQL_PORT')}/{os.getenv('MY_SQL_DB')}"
    DATABASE_USER = os.getenv("MY_SQL_USER")
    DATABASE_PASSWORD = os.getenv("MY_SQL_PASSWORD")
    DATABASE_HOST = os.getenv("MY_SQL_HOST")
    DATABASE_PORT = os.getenv("MY_SQL_PORT")
    DATABASE_NAME = os.getenv("MY_SQL_db")

    HASH_SECRET_KEY = os.getenv("HASH_SECRET_KEY")
    HASH_ALGORITHM = os.getenv("HASH_ALGORITHM")
    TOKEN_EXPIRY_TIME = os.getenv("TOKEN_EXPIRY_TIME")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
    LLM_MODEL = os.getenv("LLM_MODEL")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")


config = Config()

logger.info(
    f"Config loaded | DB Host={config.DATABASE_HOST}, DB Name={config.DATABASE_NAME}, "
    f"Embedding Model={config.EMBEDDING_MODEL}"
)