from fastapi import APIRouter, Depends, Query
from src.schema.log_schema import LogRead
from sqlmodel.ext.asyncio.session import AsyncSession
from src.services.log_service import LogService
from src.repositories.log_repository import LogRepo
from src.Database.base_db import Database
from typing import Annotated, Optional
from src.Database import system_db as db
from src.security.o_auth import auth_dependency



router = APIRouter(prefix="/logs", tags=["Logs"])


def get__log_service(session: AsyncSession = Depends(db.get_session)) -> LogService:
    return LogService(session)

log_session = Annotated[LogService, Depends(get__log_service)]


@router.get("/get-logs", response_model=list[LogRead])
async def get_logs(
    service: log_session,
    client_id: Optional[str] = Query(default=None),
):
    return await service.get_logs(client_id=client_id)
