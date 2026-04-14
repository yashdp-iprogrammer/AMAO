import os
import json
import asyncio
from cachetools import TTLCache
from collections import defaultdict

from src.vector_db.base import BaseVectorStore
from langchain_community.vectorstores import FAISS
from transformers import logging as hf_logging
from src.utils.logger import logger

hf_logging.set_verbosity_error()


class FaissVectorStore(BaseVectorStore):

    # -------------------------
    # SHARED CACHE (TTL + LRU)
    # -------------------------
    _cache = TTLCache(maxsize=50, ttl=1800)

    # -------------------------
    # PER CLIENT LOCKS
    # -------------------------
    _client_locks = defaultdict(asyncio.Lock)

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

    # -------------------------
    # SAFE LOAD STORE
    # -------------------------
    async def _load_store(self, client_id, faiss_path):

        # FAST PATH
        cached = self._cache.get(client_id)
        if cached:
            logger.info(f"[FAISS] Cache hit | client_id={client_id}")
            return cached

        client_lock = self._client_locks[client_id]

        async with client_lock:

            # DOUBLE CHECK
            cached = self._cache.get(client_id)
            if cached:
                return cached

            index_file = os.path.join(faiss_path, "index.faiss")

            if not os.path.exists(index_file):
                logger.warning(f"[FAISS] No index file found | client_id={client_id}")
                return None

            logger.info(f"[FAISS] Loading FAISS index | client_id={client_id}")

            try:
                vector_store = FAISS.load_local(
                    faiss_path,
                    embeddings=self.embedding,
                    allow_dangerous_deserialization=True
                )
            except Exception:
                logger.exception(f"[FAISS] Failed to load FAISS index | client_id={client_id}")
                return None

            self._cache[client_id] = vector_store
            return vector_store

    # -------------------------
    # SAFE INVALIDATION
    # -------------------------
    async def _invalidate_cache(self, client_id):

        client_lock = self._client_locks[client_id]

        async with client_lock:

            if client_id in self._cache:
                logger.info(f"[FAISS] Cache invalidated | client_id={client_id}")
                self._cache.pop(client_id, None)


    # -------------------------
    # APPEND
    # -------------------------
    async def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

        logger.info(f"[FAISS] Append start | client_id={client_id}, document={document_name}")

        faiss_path, docs_path = self._get_vector_path(client_id)
        hash_path = os.path.join(docs_path, f"{document_name}.hashes")

        if paragraphs is None:
            logger.info("[FAISS] Skipping update (already processed)")
            return "File already processed"

        new_hash_map = {p["hash"]: p["text"] for p in paragraphs}
        new_hashes = set(new_hash_map.keys())

        vector_store = await self._load_store(client_id, faiss_path)

        before_count = vector_store.index.ntotal if vector_store else 0

        # -----------------------------
        # EXISTING FILE
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
                vector_store.delete(ids=list(deleted))

        # -----------------------------
        # NEW FILE
        # -----------------------------
        else:

            existing_hashes = set(vector_store.docstore._dict.keys()) if vector_store else set()
            added = new_hashes - existing_hashes

        # -----------------------------
        # ADD
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
        # SAVE
        # -----------------------------
        if vector_store:
            try:
                vector_store.save_local(faiss_path)
            except Exception:
                logger.exception(f"[FAISS] Failed to save index | client_id={client_id}")

        with open(hash_path, "w") as f:
            json.dump(new_hash_map, f)

        await self._invalidate_cache(client_id)

        return "Incremental update complete"

    # -------------------------
    # RETRIEVE
    # -------------------------
    async def retrieve(self, client_id, query, top_k=5):

        logger.info(f"[FAISS] Retrieve | client_id={client_id}, top_k={top_k}")

        faiss_path, _ = self._get_vector_path(client_id)

        vector_db = await self._load_store(client_id, faiss_path)

        if not vector_db:
            return []

        try:
            return vector_db.similarity_search(query, k=top_k)
        except Exception:
            logger.exception("[FAISS] Retrieval failed")
            return []