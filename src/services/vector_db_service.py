from src.vector_db.faiss_store import FaissVectorStore
from src.vector_db.chroma_store import ChromaVectorStore
from src.utils.logger import logger


class VectorDBService:

    def __init__(self, db_type: str):
        logger.info(f"[VectorDBService] Initializing VectorDBService with db_type: {db_type}")

        if db_type == "faiss":
            self.store = FaissVectorStore()

        elif db_type == "chroma":
            self.store = ChromaVectorStore()

        else:
            logger.warning(f"[VectorDBService] Unsupported vector DB type: {db_type}")
            raise ValueError(f"Unsupported vector DB: {db_type}")

    def append_to_store(self, client_id, document_name, texts):
        logger.info(f"[VectorDBService] Appending to vector store | client_id={client_id}, document={document_name}")

        return self.store.append_to_store(
            client_id,
            document_name,
            texts,
        )

    def retrieve(self, client_id, query, top_k):
        logger.info(f"[VectorDBService] Retrieving from vector store | client_id={client_id}, top_k={top_k}")

        return self.store.retrieve(
            client_id,
            query,
            top_k
        )