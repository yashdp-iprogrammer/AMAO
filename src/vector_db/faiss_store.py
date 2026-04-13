import os
import json
from src.vector_db.base import BaseVectorStore
from langchain_community.vectorstores import FAISS
from transformers import logging as hf_logging
from src.utils.logger import logger

hf_logging.set_verbosity_error()


class FaissVectorStore(BaseVectorStore):
    
    def __init__(self):
        super().__init__()
        self.embedding = self._get_embedding()
    
    def _get_vector_path(self, client_id):

        client_root = self._get_client_root(client_id)
        faiss_path = os.path.join(client_root, "faiss")
        
        docs_path = os.path.join(faiss_path, "hashes")
        os.makedirs(faiss_path, exist_ok=True)
        os.makedirs(docs_path, exist_ok=True)

        return faiss_path, docs_path


    def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

        logger.info(f"[FAISS] Faiss append start | client_id={client_id}, document={document_name}")

        faiss_path, docs_path = self._get_vector_path(client_id)
        hash_path = os.path.join(docs_path, f"{document_name}.hashes")

        if paragraphs is None:
            logger.info("[FAISS] Skipping update (file already processed)")
            return "File already processed"

        new_hash_map = {p["hash"]: p["text"] for p in paragraphs}
        new_hashes = set(new_hash_map.keys())

        index_file = os.path.join(faiss_path, "index.faiss")

        vector_store = None
        before_count = 0

        if os.path.exists(index_file):
            logger.info("[FAISS] Loading existing FAISS index")

            vector_store = FAISS.load_local(
                faiss_path,
                embeddings=self.embedding,
                allow_dangerous_deserialization=True
            )

            before_count = vector_store.index.ntotal
            logger.info(f"[FAISS] Embeddings before update: {before_count}")

        else:
            logger.warning("[FAISS] No existing FAISS index found")

        # -----------------------------
        # CASE 1: SAME FILENAME UPDATE
        # -----------------------------
        if os.path.exists(hash_path):

            logger.info("[FAISS] Existing document detected, running incremental diff")

            with open(hash_path, "r") as f:
                old_hash_map = json.load(f)

            old_hashes = set(old_hash_map.keys())

            added = new_hashes - old_hashes
            deleted = old_hashes - new_hashes

            if not added and not deleted:
                logger.info("[FAISS] No document changes detected")
                return "No changes detected"

            logger.info(f"[FAISS] Diff summary | added={len(added)}, deleted={len(deleted)}")

            if deleted and vector_store:
                logger.info(f"[FAISS] Deleting {len(deleted)} embeddings for document={document_name}")
                vector_store.delete(ids=list(deleted))

        # -----------------------------
        # CASE 2: NEW FILENAME
        # -----------------------------
        else:

            logger.info("[FAISS] New document detected")

            if vector_store:
                existing_hashes = set(vector_store.docstore._dict.keys())
            else:
                existing_hashes = set()

            added = new_hashes - existing_hashes
            deleted = set()

            logger.info(f"[FAISS] Duplicate check | total={len(new_hashes)}, new={len(added)}, existing={len(new_hashes - added)}")

        # -----------------------------
        # ADD NEW EMBEDDINGS
        # -----------------------------
        if added:

            texts = [new_hash_map[h] for h in added]
            ids = list(added)
            metadatas = [{"doc": document_name, "para_hash": h} for h in added]

            if vector_store:
                logger.info(f"[FAISS] Adding {len(texts)} embeddings")
                vector_store.add_texts(texts=texts, ids=ids, metadatas=metadatas)

            else:
                logger.info("[FAISS] Creating new FAISS store")

                vector_store = FAISS.from_texts(
                    texts,
                    embedding=self.embedding,
                    ids=ids,
                    metadatas=metadatas
                )

        # -----------------------------
        # SAVE INDEX
        # -----------------------------
        if vector_store:

            after_count = vector_store.index.ntotal
            change = after_count - before_count

            logger.info(f"[FAISS] Embeddings after update: {after_count}")
            logger.info(f"[FAISS] Net embedding change: {change}")

            vector_store.save_local(faiss_path)

            logger.info("[FAISS] Faiss index saved successfully")

        # -----------------------------
        # SAVE DOCUMENT STRUCTURE
        # -----------------------------
        with open(hash_path, "w") as f:
            json.dump(new_hash_map, f)

        logger.info("[FAISS] Faiss update complete")

        return "Incremental update complete"


    def retrieve(self, client_id, query, top_k=5):

        logger.info(f"[FAISS] Faiss retrieve | client_id={client_id}, top_k={top_k}, question={query}")

        faiss_path, _ = self._get_vector_path(client_id)
        index_file = os.path.join(faiss_path, "index.faiss")

        if not os.path.exists(index_file):
            logger.warning(f"[FAISS] Faiss index not found for client_id={client_id}")
            return []

        try:
            vector_db = FAISS.load_local(
                faiss_path,
                embeddings=self.embedding,
                allow_dangerous_deserialization=True
            )

            docs = vector_db.similarity_search(query, k=top_k)

            logger.info(f"[FAISS] Retrieved {len(docs)} documents from FAISS")

            return docs

        except Exception:
            logger.exception("[FAISS] Error during FAISS retrieval")
            return []