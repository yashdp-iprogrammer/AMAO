from uuid import uuid4
from datetime import datetime, timezone
from src.Database.models import Log
from src.repositories.log_repository import LogRepo
from src.utils.logger import logger


class LogService:

    def __init__(self, session):
        self.log_repo = LogRepo(session)

    async def add_log(self, data):
        logger.info("Creating new log entry")

        log = Log(
            log_id=str(uuid4()),
            **data.dict(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        created_log = await self.log_repo.add_log(log)

        logger.info(f"[LOG] Log created successfully: {log.log_id}")

        return created_log

    async def get_logs(self, client_id: str):
        if client_id:
            logger.info(f"[LOG] Fetching logs for client_id: {client_id}")
            return await self.log_repo.get_logs(client_id)

        logger.info("[LOG] Fetching all logs")
        return await self.log_repo.get_logs()