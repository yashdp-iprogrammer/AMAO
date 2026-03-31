import os
from abc import ABC, abstractmethod
from src.settings.config import config
from langchain_huggingface.embeddings import HuggingFaceEmbeddings


class BaseVectorStore(ABC):

    _embedding = None

    def __init__(self):
        self.base_path = os.path.abspath(config.VECTOR_DB_PATH)

    def _get_embedding(self):

        if BaseVectorStore._embedding is None:
            print("[VectorDB] Loading embedding model...")
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