from typing import Annotated
from src.utils.logger import logger
from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from src.services.client_service import ClientService
from src.schema.client_schema import ClientCreate, ClientResponseList, ClientResponse
from src.schema.client_schema import ClientCreate, ClientUpdate, ClientRead
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
    logger.info(f"API call to create client: {client.client_name}")
    return await service.create_client(client)


@router.put("/update-client/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    client: ClientUpdate,
    service: client_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    return await service.update_client(client_id, client)


@router.delete("/remove-client/{client_id}")
async def delete_client(
    client_id: str,
    service: client_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    return await service.delete_client(client_id)


@router.get("/list-clients", response_model=ClientResponseList)
async def get_all_clients(
    service: client_session,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    return await service.get_all_clients(page, size)


@router.get("/get-client/{client_id}", response_model=ClientRead)
async def get_client_by_id(
    client_id: str,
    service: client_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    return await service.get_client_by_id(client_id)


@router.get("/connect/{client_id}")
async def connect_client_db(
    client_id: str,
    config_service: config_session,
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin", "User"]))
):

    connections = connection_manager.get_client_connections(
        client_id,
        current_user
    )
    
    # print(client_db)

    # async with client_db.session_scope() as session:
    #     result = await session.exec(text("SELECT 1"))
    #     value = result.one()[0]

    # return {
    #     "message": "Connected successfully",
    #     "client_id": client_id,
    #     "test_query_result": value
    # }
    
    return {
        "message":"Connections created successfully"
    }
