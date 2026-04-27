from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from src.repositories.client_repository import ClientRepo
from src.repositories.user_repository import UserRepo
from src.services.config_service import ConfigService
from src.Database.models import Client
from src.schema.client_schema import ClientCreate, ClientUpdate
from src.utils.logger import logger
from src.utils.hash_util import hash_util


class ClientService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client_repo = ClientRepo(session)
        self.user_repo = UserRepo(session)
        self.config_service = ConfigService(session)
        self.hash_handler = hash_util


    async def create_client(self, client: ClientCreate) -> Client:
        logger.info(f"[CLIENT] Creating client: {client.client_name}")

        existing = await self.client_repo.get_client_by_email(client)
        if existing:
            raise HTTPException(status_code=400, detail="Client already exists")

        hashed_password = self.hash_handler.get_password_hash(client.password)

        client_dict = client.model_dump()

        client_dict["allowed_agents"] = {
            k: v.model_dump(exclude_none=True)
            for k, v in client.allowed_agents.items()
        }

        client_obj = Client(
            client_id=str(uuid4()),
            client_name=client_dict["client_name"],
            client_email=client_dict["client_email"],
            phone=client_dict["phone"],
            password=hashed_password,
            allowed_agents=client_dict["allowed_agents"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        created_client = await self.client_repo.create_client(client_obj)

        try:
            await self.config_service.upsert_config(
                client_id=created_client.client_id,
                allowed_agents=client_dict["allowed_agents"]
            )

        except Exception:
            logger.exception("[CLIENT] Config creation failed after client creation")

            await self.client_repo.delete_client(created_client)

            raise HTTPException(
                status_code=500,
                detail="Client created but config failed. Rolled back."
            )

        logger.info(f"[CLIENT] Client + Config created successfully: {client.client_name}")

        return {
            "message": "Client created successfully",
            "client": created_client
        }


    async def update_client(self, client_id: str, client: ClientUpdate):
        logger.info(f"[CLIENT] Updating client: {client_id}")

        existing_client = await self.client_repo.get_client_by_id(client_id)

        if not existing_client:
            raise HTTPException(status_code=404, detail="Client not found")

        updated_client = await self.client_repo.update_client(existing_client, client)
        
        if client.allowed_agents:
            try:
                await self.config_service.upsert_config(
                    client_id=updated_client.client_id,
                    client_name=updated_client.client_name,
                    allowed_agents=client.allowed_agents
                )

            except Exception:
                logger.exception("[CLIENT] Config creation failed during update")
                raise HTTPException(
                    status_code=500,
                    detail="Client updated but config failed"
                )

        logger.info(f"[CLIENT] Client updated successfully: {client_id}")

        return {
            "message": "Client updated successfully",
            "client": updated_client
        }
    
    
    async def delete_client(self, client_id: str):
        logger.info(f"[CLIENT] Deleting client: {client_id}")

        existing_client = await self.client_repo.get_client_by_id(client_id)

        if not existing_client:
            raise HTTPException(status_code=404, detail="Client not found")

        await self.user_repo.delete_users_by_client_id(client_id)

        existing_client.is_disabled = True
        existing_client.updated_at = datetime.now(timezone.utc)

        self.session.add(existing_client)

        await self.session.commit()

        logger.info(f"[CLIENT] Client + Users deleted: {client_id}")

        return {"message": "Client and its users deleted successfully"}
    

    async def get_all_clients(self, page: int, size: int):
        logger.info(f"[CLIENT] Fetching all clients | page={page}, size={size}")
        return await self.client_repo.get_all_clients(page, size)


    async def get_client_by_id(self, client_id: str):
        logger.info(f"[CLIENT] Fetching client by id: {client_id}")
        client = await self.client_repo.get_client_by_id(client_id)

        if not client:
            logger.warning(f"[CLIENT] Client not found: {client_id}")
            raise HTTPException(status_code=404, detail="Client not found")

        return client
