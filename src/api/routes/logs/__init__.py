from fastapi import APIRouter, Depends, Query
from src.schema.log_schema import LogRead
from sqlmodel.ext.asyncio.session import AsyncSession
from src.services.log_service import LogService
from typing import Annotated, Optional
from src.Database import system_db as db
from src.security.o_auth import auth_dependency
from src.schema.user_schema import CurrentUser
from src.utils.logger import logger



router = APIRouter(prefix="/logs", tags=["Logs"])


def get__log_service(session: AsyncSession = Depends(db.get_session)) -> LogService:
    return LogService(session)

log_session = Annotated[LogService, Depends(get__log_service)]


@router.get("/get-logs", response_model=list[LogRead])
async def get_logs(
    service: log_session,
    client_id: Optional[str] = Query(default=None),
    current_user: CurrentUser = Depends(auth_dependency.require_roles(["SuperAdmin", "Admin"]))
):
    if client_id:
        logger.info(f"[GET_LOGS] user_id={current_user.user_id}, client_id={client_id}")
    else:
        logger.info(f"[GET_LOGS] user_id={current_user.user_id}, fetching all logs")
        
    return await service.get_logs(client_id)
