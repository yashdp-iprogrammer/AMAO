from typing import Annotated
from src.utils.logger import logger
from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from src.services.client_service import ClientService
from src.schema.client_schema import ClientCreate,ClientUpdate,ClientRead,ClientResponse,ClientResponseList
from src.Database import system_db as db
from src.services.config_service import ConfigService
from src.Database.connection_manager import ConnectionManager
from src.security.o_auth import auth_dependency


router = APIRouter(prefix="/clients", tags=["Clients"])


def get_client_service(session: AsyncSession = Depends(db.get_session)) -> ClientService:
    return ClientService(session)

client_session = Annotated[ClientService, Depends(get_client_service)]

def get_config_service(session: AsyncSession = Depends(db.get_session)) -> ConfigService:
    return ConfigService(session)

config_session = Annotated[ConfigService, Depends(get_config_service)]

def get_connection_manager(config_service: ConfigService = Depends(get_config_service)):
    return ConnectionManager(config_service)


@router.post("/add-client", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    service: client_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[CREATE_CLIENT] user={current_user}, client_name={client.client_name}")

    result = await service.create_client(client)

    return result


@router.put("/update-client/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    client: ClientUpdate,
    service: client_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[UPDATE_CLIENT] user={current_user}, client_id={client_id}")

    result = await service.update_client(client_id, client)

    return result


@router.delete("/remove-client/{client_id}")
async def delete_client(
    client_id: str,
    service: client_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[DELETE_CLIENT] user={current_user}, client_id={client_id}")

    result = await service.delete_client(client_id)

    return result


@router.get("/list-clients", response_model=ClientResponseList)
async def get_all_clients(
    service: client_session,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[LIST_CLIENTS] user={current_user}, page={page}, size={size}")

    result = await service.get_all_clients(page, size)

    return result


@router.get("/get-client/{client_id}", response_model=ClientRead)
async def get_client_by_id(
    client_id: str,
    service: client_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[GET_CLIENT] user={current_user}, client_id={client_id}")

    result = await service.get_client_by_id(client_id)

    return result


@router.get("/connect/{client_id}")
async def connect_client_db(
    client_id: str,
    config_service: config_session,
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin", "User"]))
):
    logger.info(f"[CONNECT_CLIENT] user={current_user}, client_id={client_id}")

    connections = connection_manager.get_client_connections(
        client_id,
        current_user
    )

    return {
        "message": "Connections created successfully"
    }
