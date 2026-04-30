from src.vector_db.vectordb_registry import get_vector_store
from src.utils.logger import logger


class VectorDBService:

    def __init__(self, store):
        self.store = store

    @classmethod
    async def create(cls, client_id: str, db_type: str, db_config: dict = None):
        logger.info(f"[VectorDBService] Initializing with db_type: {db_type}")

        store = await get_vector_store(client_id, db_type, db_config)

        return cls(store)

    async def append_to_store(self, client_id, document_name, texts):
        logger.info(f"[VectorDBService] Appending to vector store | client_id={client_id}, document={document_name}")

        return await self.store.append_to_store(client_id, document_name, texts)

    async def retrieve(self, client_id, query, top_k):
        logger.info(f"[VectorDBService] Retrieving from vector store | client_id={client_id}, top_k={top_k}")

        return await self.store.retrieve(client_id, query, top_k)