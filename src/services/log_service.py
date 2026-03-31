from uuid import uuid4
from datetime import datetime, timezone
from src.Database.models import Log
from src.repositories.log_repository import LogRepo


class LogService:

    def __init__(self, session):
        self.log_repo = LogRepo(session)

    async def add_log(self, data):
        log = Log(
            log_id=str(uuid4()),
            **data.dict(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),

        )
        return await self.log_repo.add_log(log)

    async def get_logs(self, client_id: str):
        if client_id:
            return await self.log_repo.get_logs(client_id)
        return await self.log_repo.get_logs()

    # async def main(self, session, data):
    #     service = LogService(session)
    #     await service.add_log(data)
