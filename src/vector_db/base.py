import os
from abc import ABC, abstractmethod
from src.settings.config import config
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from src.utils.logger import logger


class BaseVectorStore(ABC):

    _embedding = None

    def __init__(self):
        self.base_path = os.path.abspath(config.VECTOR_DB_PATH)

    @classmethod
    def warmup_embedding(cls):
        if cls._embedding is None:
            logger.info(f"PRE-WARM: Loading embedding model: {config.EMBEDDING_MODEL}")
            cls._embedding = HuggingFaceEmbeddings(
                model_name=config.EMBEDDING_MODEL
            )
            # force actual model load
            _ = cls._embedding.embed_query("warmup")
            logger.info("PRE-WARM: Embedding model loaded")

    def _get_embedding(self):

        if BaseVectorStore._embedding is None:
            logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL}")
            
            BaseVectorStore._embedding = HuggingFaceEmbeddings(
                model_name=config.EMBEDDING_MODEL
            )

        return BaseVectorStore._embedding

    def _get_client_root(self, client_id: str):
        return os.path.join(self.base_path, f"client_id_{client_id}")

    @abstractmethod
    def append_to_store(self, client_id: str, document_name: str, paragraphs: list):
        pass

    @abstractmethod
    def retrieve(self, client_id: str, user_question: str, top_k: int = 3):
        pass