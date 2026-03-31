from datetime import datetime, timezone
from sqlmodel import select, func
from src.utils.hash_util import PasswordHandler
from src.utils.logger import logger
from src.Database.models import Client
from src.schema.client_schema import ClientCreate, ClientUpdate
from sqlmodel.ext.asyncio.session import AsyncSession
from src.utils.hash_util import hash_util


class ClientRepo:
    def __init__(self, session: AsyncSession):
        self.session = session
        # self.hash_handler = PasswordHandler()
        self.hash_handler = hash_util

    async def create_client(self, client: Client) -> Client:
        logger.info(f"Adding client with client_id={client.client_id}")
        try:    
            self.session.add(client)
            await self.session.commit()
            await self.session.refresh(client)
            logger.info("Client added successfully")
            return client
        except Exception as e:
            logger.exception(f"Failed to add client: {e}")
            raise
        
        
    async def update_client(self, existing_client: Client, client: ClientUpdate):
        update_data = client.model_dump(exclude_unset=True)
        
        password = update_data.pop("client_password", None)
        if password:
            existing_client.password = self.hash_handler.get_password_hash(password)


        for key, value in update_data.items():
            setattr(existing_client, key, value)

        existing_client.updated_at = datetime.now(timezone.utc)
        
        self.session.add(existing_client)
        await self.session.commit()
        await self.session.refresh(existing_client)
        return existing_client


    async def delete_client(self, existing_client: Client):
        existing_client.is_disabled = True
        existing_client.updated_at = datetime.now(timezone.utc)
        self.session.add(existing_client)
        await self.session.commit()


    async def get_all_clients(self, page: int, size: int):

        statement = select(Client).where(Client.is_disabled == False)

        count_stmt = select(func.count()).select_from(statement.subquery())
        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        offset = (page - 1) * size

        statement = statement.offset(offset).limit(size)

        result = await self.session.exec(statement)
        clients = result.all()
        
        total_pages = (total + size - 1) // size

        return {
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "data": clients
        }
    
    
    async def get_client_by_id(self, client_id: str):
        statement = select(Client).where(
            Client.client_id == client_id,
            Client.is_disabled == False
        )        
        result = await self.session.exec(statement)
        return result.one_or_none()


    async def get_client_by_email(self, client: ClientCreate):
        statement = select(Client).where(Client.client_email == client.client_email, Client.is_disabled == False)
        result = await self.session.exec(statement)
        return result.one_or_none()