from src.Database.base_db import Database
from src.settings.config import config
from src.utils.logger import logger

logger.info("[system_db] Initializing system database")

system_db = Database(config.DATABASE_URL)
