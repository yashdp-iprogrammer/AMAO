import dotenv
import os
from src.utils.logger import logger
dotenv.load_dotenv()

if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true":
    if not os.getenv("LANGCHAIN_API_KEY"):
        logger.warning("LangSmith tracing enabled but LANGCHAIN_API_KEY is not set")
    else:
        logger.info("LangSmith tracing is enabled")

required_vars = ["MY_SQL_USER", "MY_SQL_PASSWORD", "MY_SQL_HOST","MY_SQL_PORT", "MY_SQL_DB"]

missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    raise ValueError(f"Missing required environment variables: {missing}")


class Config:
    DATABASE_USER = os.getenv("MY_SQL_USER")
    DATABASE_PASSWORD = os.getenv("MY_SQL_PASSWORD")
    DATABASE_HOST = os.getenv("MY_SQL_HOST")
    DATABASE_PORT = os.getenv("MY_SQL_PORT")
    DATABASE_NAME = os.getenv("MY_SQL_DB")

    DATABASE_URL = f"mysql+aiomysql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
    
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