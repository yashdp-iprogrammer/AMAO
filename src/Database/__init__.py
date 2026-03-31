from src.Database.base_db import Database
from src.settings.config import config

system_db = Database(config.DATABASE_URL)
