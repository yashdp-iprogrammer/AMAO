from src.vector_db.faiss_store import FaissVectorStore
from src.vector_db.chroma_store import ChromaVectorStore


class VectorDBService:

    def __init__(self, db_type: str):

        if db_type == "faiss":
            self.store = FaissVectorStore()

        elif db_type == "chroma":
            self.store = ChromaVectorStore()

        else:
            raise ValueError(f"Unsupported vector DB: {db_type}")

    def append_to_store(self, client_id, document_name, texts):

        return self.store.append_to_store(
            client_id,
            document_name,
            texts,
        )

    def retrieve(self, client_id, query, top_k):

        return self.store.retrieve(
            client_id,
            query,
            top_k
        )