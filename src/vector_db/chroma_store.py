import os
import json
import asyncio
from cachetools import TTLCache
from collections import defaultdict

from langchain_chroma import Chroma
from src.vector_db.base import BaseVectorStore
from transformers import logging as hf_logging
from src.utils.logger import logger

hf_logging.set_verbosity_error()


class ChromaVectorStore(BaseVectorStore):

    # -------------------------
    # CACHE
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
        
        chroma_path = os.path.join(client_root, "chroma")
        docs_path = os.path.join(chroma_path, "hashes")
        
        os.makedirs(docs_path, exist_ok=True)
        os.makedirs(chroma_path, exist_ok=True)

        return chroma_path, docs_path

    # -------------------------
    # SAFE LOAD STORE
    # -------------------------
    async def _load_store(self, client_id, chroma_path):

        # FAST PATH
        cached = self._cache.get(client_id)
        if cached:
            logger.info(f"[CHROMA] Cache hit | client_id={client_id}")
            return cached

        client_lock = self._client_locks[client_id]

        async with client_lock:

            # DOUBLE CHECK
            cached = self._cache.get(client_id)
            if cached:
                return cached

            logger.info(f"[CHROMA] Loading store from disk | client_id={client_id}")

            try:
                vector_store = Chroma(
                    persist_directory=chroma_path,
                    embedding_function=self.embedding
                )
            except Exception:
                logger.exception(f"[CHROMA] Failed to initialize store | client_id={client_id}")
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
                logger.info(f"[CHROMA] Cache invalidated | client_id={client_id}")
                self._cache.pop(client_id, None)


    # -------------------------
    # APPEND
    # -------------------------
    async def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

        logger.info(f"[CHROMA] Append start | client_id={client_id}, document={document_name}")

        chroma_path, docs_path = self._get_vector_path(client_id)
        hash_path = os.path.join(docs_path, f"{document_name}.hashes")

        if paragraphs is None:
            logger.info("[CHROMA] Skipping update (already processed)")
            return "File already processed"

        new_hash_map = {p["hash"]: p["text"] for p in paragraphs}
        new_hashes = set(new_hash_map.keys())

        vector_store = await self._load_store(client_id, chroma_path)

        if not vector_store:
            logger.error("[CHROMA] Store not available")
            return "Vector store not available"

        before_count = vector_store._collection.count()

        # -----------------------------
        # EXISTING FILE
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
        # NEW FILE
        # -----------------------------
        else:

            logger.info("[CHROMA] New document detected")

            existing = vector_store._collection.get(include=[])
            existing_hashes = set(existing.get("ids", []))

            added = new_hashes - existing_hashes

        # -----------------------------
        # ADD
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

        logger.info(f"[CHROMA] Count before={before_count}, after={after_count}")

        # -----------------------------
        # SAVE HASH
        # -----------------------------
        with open(hash_path, "w") as f:
            json.dump(new_hash_map, f)

        await self._invalidate_cache(client_id)

        return "Incremental update complete"

    # -------------------------
    # RETRIEVE
    # -------------------------
    async def retrieve(self, client_id, query, top_k):
        
        logger.info(f"[CHROMA] Retrieve | client_id={client_id}, top_k={top_k}, question={query}")

        chroma_path, _ = self._get_vector_path(client_id)

        vector_store = await self._load_store(client_id, chroma_path)

        if not vector_store:
            return []

        try:
            docs = vector_store.similarity_search(query, k=top_k)
            return docs
        except Exception:
            logger.exception("[CHROMA] Retrieval failed")
            return []