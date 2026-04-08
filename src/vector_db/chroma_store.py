import os
import json
from langchain_chroma import Chroma
from src.vector_db.base import BaseVectorStore
from transformers import logging as hf_logging
from src.utils.logger import logger

hf_logging.set_verbosity_error()


class ChromaVectorStore(BaseVectorStore):
    
    def __init__(self):
        super().__init__()
        self.embedding = self._get_embedding()

    def _get_vector_path(self, client_id):
        client_root = self._get_client_root(client_id)
        
        chroma_path = os.path.join(client_root, "chroma")
        docs_path = os.path.join(chroma_path, "hashes")
        
        os.makedirs(docs_path, exist_ok=True)
        os.makedirs(chroma_path, exist_ok=True)
        
        return chroma_path, docs_path
    

    def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

        logger.info(f"[CHROMA] Chroma append start | client_id={client_id}, document={document_name}")

        chroma_path, docs_path = self._get_vector_path(client_id)
        hash_path = os.path.join(docs_path, f"{document_name}.hashes")

        new_hash_map = {p["hash"]: p["text"] for p in paragraphs}
        new_hashes = set(new_hash_map.keys())

        vector_store = Chroma(
            persist_directory=chroma_path,
            embedding_function=self.embedding
        )

        before_count = vector_store._collection.count()
        logger.info(f"[CHROMA] Embeddings before update: {before_count}")

        # -----------------------------
        # CASE 1: SAME FILENAME UPDATE
        # -----------------------------
        if os.path.exists(hash_path):

            logger.info("[CHROMA] Existing document detected, running incremental diff")

            with open(hash_path, "r") as f:
                old_hash_map = json.load(f)

            old_hashes = set(old_hash_map.keys())

            added = new_hashes - old_hashes
            deleted = old_hashes - new_hashes

            if not added and not deleted:
                logger.info("[CHROMA] No document changes detected")
                return "No changes detected"

            logger.info(f"[CHROMA] Diff summary | added={len(added)}, deleted={len(deleted)}")

            if deleted:
                logger.info(f"[CHROMA] Deleting {len(deleted)} embeddings")
                vector_store.delete(ids=list(deleted))

        # -----------------------------
        # CASE 2: NEW FILENAME
        # -----------------------------
        else:

            logger.info("[CHROMA] New document detected")

            existing = vector_store._collection.get(include=[])
            existing_hashes = set(existing["ids"])

            added = new_hashes - existing_hashes
            deleted = set()

            logger.info(f"[CHROMA] Duplicate check | total={len(new_hashes)}, new={len(added)}, existing={len(new_hashes - added)}")

        # -----------------------------
        # ADD NEW EMBEDDINGS
        # -----------------------------
        if added:

            texts = [new_hash_map[h] for h in added]
            ids = list(added)
            metadatas = [{"doc": document_name, "para_hash": h} for h in added]

            logger.info(f"[CHROMA] Adding {len(texts)} embeddings")

            vector_store.add_texts(
                texts=texts,
                ids=ids,
                metadatas=metadatas
            )

        after_count = vector_store._collection.count()
        change = after_count - before_count

        logger.info(f"[CHROMA] Embeddings after update: {after_count}")
        logger.info(f"[CHROMA] Net embedding change: {change}")

        # -----------------------------
        # SAVE HASH FILE
        # -----------------------------
        with open(hash_path, "w") as f:
            json.dump(new_hash_map, f)

        logger.info("[CHROMA] Chroma update complete")

        return "Incremental update complete"


    def retrieve(self, client_id, query, top_k):
        logger.info(f"[CHROMA] Chroma retrieve | client_id={client_id}, top_k={top_k}, question={query}")

        chroma_path, _ = self._get_vector_path(client_id)

        vector_store = Chroma(
            persist_directory=chroma_path,
            embedding_function=self.embedding
        )

        docs = vector_store.similarity_search(query, k=top_k)

        logger.info(f"[CHROMA] Retrieved {len(docs)} documents from Chroma")

        return docs