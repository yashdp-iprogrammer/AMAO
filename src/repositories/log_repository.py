from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.Database.models import Log


class LogRepo:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_log(self, log: Log):
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def get_logs(self, client_id: str):
        statement = select(Log).where(Log.client_id == client_id)
        result = await self.session.exec(statement)
        return result.all()
    
    async def get_log_by_id(self, log_id: str):
        statement = select(Log).where(Log.log_id == log_id)
        result = await self.session.exec(statement)
        return result.one_or_none()

