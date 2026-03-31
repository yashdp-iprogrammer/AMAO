from fastapi import APIRouter, Depends
from src.schema.config_schema import ConfigCreate, ConfigUpdate
from src.Database import system_db as db
from src.services.config_service import ConfigService
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Annotated
from src.security.o_auth import auth_dependency



router = APIRouter(prefix="/configs", tags=["Configs"])

def get_config_service(session: AsyncSession = Depends(db.get_session)) -> ConfigService:
    return ConfigService(session)

config_session = Annotated[ConfigService, Depends(get_config_service)]


@router.post("/create-config-file/{client_id}")
async def create_config_file(client_id: str, config: ConfigCreate, config_service: config_session, current_user = Depends(auth_dependency.require_roles(["SuperAdmin"]))):
    return await config_service.create_config(client_id, config)


@router.put("/update-config-file/{client_id}")
async def update_config_file(client_id: str, config: ConfigUpdate, config_service: config_session, current_user = Depends(auth_dependency.require_roles(["SuperAdmin"]))):
    return config_service.update_config(client_id, config)


@router.delete("/remove-config-file/{client_id}")
async def remove_config_file(client_id: str, config_service: config_session, current_user = Depends(auth_dependency.require_roles(["SuperAdmin"]))):
    return config_service.remove_config(client_id)


@router.get("/read-config/{client_id}")
async def read_config(client_id: str, config_service: config_session, current_user = Depends(auth_dependency.require_roles(["SuperAdmin"]))):
    return config_service.read_config(client_id)