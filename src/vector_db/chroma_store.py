import os
import json
import asyncio
from cachetools import TTLCache
from collections import defaultdict

import chromadb
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
    # LOCKS
    # -------------------------
    _store_locks = defaultdict(asyncio.Lock)
    _write_locks = defaultdict(asyncio.Lock)

    def __init__(self, config: dict = None):
        super().__init__()
        self.embedding = self._get_embedding()
        self.config = config or {}


    def _get_mode(self):
        return self.config.get("mode")


    def _get_paths(self, client_id):
        client_root = self._get_client_root(client_id)
        mode = self._get_mode()

        if mode == "local":
            base_path = os.path.join(client_root, "chroma_local")
            chroma_path = os.path.join(base_path, "db")
            hashes_path = os.path.join(base_path, "hashes")

        elif mode == "cloud":
            base_path = os.path.join(client_root, "chroma_cloud")
            chroma_path = None
            hashes_path = os.path.join(base_path, "hashes")

        else:
            raise ValueError(f"Unsupported mode: {mode}")

        os.makedirs(hashes_path, exist_ok=True)

        global_hash_path = os.path.join(base_path, "global_hashes.json")

        if chroma_path:
            os.makedirs(chroma_path, exist_ok=True)

        return chroma_path, hashes_path, global_hash_path


    def _get_cache_key(self, client_id):
        mode = self._get_mode()

        if mode == "local":
            return f"{client_id}:local"

        return f"{client_id}:cloud:{self.config.get('tenant_id')}:{self.config.get('database')}:{self.config.get('collection_name')}"

    # -------------------------
    # CREATE STORE
    # -------------------------
    def _create_store(self, client_id, chroma_path):

        mode = self._get_mode()

        if mode == "local":
            return Chroma(
                persist_directory=chroma_path,
                embedding_function=self.embedding
            )

        elif mode == "cloud":

            api_key = self.config.get("vectordb_api_key")
            tenant = self.config.get("tenant_id")
            database = self.config.get("database")
            collection_name = self.config.get("collection_name")

            if not api_key or not tenant or not database or not collection_name:
                raise ValueError(
                    "Cloud mode requires: api_key, tenant, database, collection_name"
                )

            try:
                client = chromadb.CloudClient(
                    tenant=tenant,
                    database=database,
                    api_key=api_key
                )
            except Exception:
                logger.exception("[CHROMA CLOUD] Failed to initialize client")
                raise

            # -------------------------
            # CHECK / CREATE COLLECTION
            # -------------------------
            try:
                client.get_collection(name=collection_name)
                logger.info(f"[CHROMA CLOUD] Collection exists: {collection_name}")
            except Exception:
                try:
                    client.create_collection(name=collection_name)
                    logger.info(f"[CHROMA CLOUD] Created collection: {collection_name}")
                except Exception:
                    logger.exception("[CHROMA CLOUD] Failed to create collection")
                    raise

            return Chroma(
                client=client,
                collection_name=collection_name,
                embedding_function=self.embedding
            )

        else:
            raise ValueError(f"Unsupported mode: {mode}")

    # -------------------------
    # LOAD STORE
    # -------------------------
    async def _load_store(self, client_id):

        chroma_path, _, _ = self._get_paths(client_id)
        cache_key = self._get_cache_key(client_id)

        if cache_key in self._cache:
            return self._cache[cache_key]

        async with self._store_locks[cache_key]:

            if cache_key in self._cache:
                return self._cache[cache_key]

            try:
                store = self._create_store(client_id, chroma_path)
            except Exception:
                logger.exception("[CHROMA] Store init failed")
                return None

            self._cache[cache_key] = store
            return store

    # -------------------------
    # GLOBAL HASH
    # -------------------------
    async def _load_global_hash(self, global_hash_path):

        async with self._write_locks["global_hash"]:

            if not os.path.exists(global_hash_path):
                return set()

            def _read():
                with open(global_hash_path, "r") as f:
                    return set(json.load(f))

            return await asyncio.to_thread(_read)

    async def _save_global_hash(self, global_hash_path, hash_set):

        async with self._write_locks["global_hash"]:

            def _write():
                with open(global_hash_path, "w") as f:
                    json.dump(list(hash_set), f)

            await asyncio.to_thread(_write)

    # -------------------------
    # INVALIDATE CACHE
    # -------------------------
    async def _invalidate_cache(self, client_id):

        prefix = f"{client_id}"

        for key in list(self._cache.keys()):
            if key.startswith(prefix):
                self._cache.pop(key, None)

    # -------------------------
    # APPEND
    # -------------------------
    async def append_to_store(self, client_id, document_name, paragraphs):

        chroma_path, hashes_path, global_hash_path = self._get_paths(client_id)
        hash_file = os.path.join(hashes_path, f"{document_name}.hashes")

        if paragraphs is None:
            return "File already processed"

        # -------------------------
        # BUILD SAFE MAP
        # -------------------------
        new_map = {}
        for p in paragraphs:
            h = p.get("hash")
            t = p.get("text")

            if not h or t is None:
                continue

            new_map[str(h)] = str(t)

        new_hashes = set(new_map.keys())

        logger.info("[DEBUG] Before load store")
        store = await self._load_store(client_id)
        logger.info("[DEBUG] After load store")

        if not store:
            return "Store unavailable"

        global_hashes = await self._load_global_hash(global_hash_path)
        logger.info("[DEBUG] Loaded global hash")

        # -------------------------
        # EXISTING FILE
        # -------------------------
        if os.path.exists(hash_file):

            try:
                with open(hash_file, "r") as f:
                    old_map = json.load(f)
            except Exception:
                old_map = {}

            old_hashes = set(old_map.keys())

            added = new_hashes - old_hashes
            deleted = old_hashes - new_hashes

            # SAFE DELETE
            if deleted:
                try:
                    await asyncio.to_thread(store.delete, list(deleted))
                except Exception:
                    logger.exception("[CHROMA] Delete failed")

            global_hashes -= deleted

        # -------------------------
        # NEW FILE
        # -------------------------
        else:
            added = new_hashes - global_hashes

        # -------------------------
        # ADD
        # -------------------------
        if added:
            texts = []
            ids = []
            metas = []

            for h in sorted(added):
                text = new_map.get(h)
                if text is None:
                    continue

                texts.append(text)
                ids.append(h)
                metas.append({"doc": document_name, "para_hash": h})

            if texts:
                try:
                    logger.info(f"[DEBUG] Upserting {len(texts)} chunks")
                    await asyncio.to_thread(
                        store.add_texts,
                        texts,
                        ids=ids,
                        metadatas=metas
                    )
                    global_hashes.update(added)
                except Exception:
                    logger.exception("[CHROMA] Add failed")


        # -------------------------
        # SAVE FILE HASH
        # -------------------------
        def _write_file():
            with open(hash_file, "w") as f:
                json.dump(new_map, f)

        await asyncio.to_thread(_write_file)

        # -------------------------
        # SAVE GLOBAL HASH
        # -------------------------
        await self._save_global_hash(global_hash_path, global_hashes)

        await self._invalidate_cache(client_id)

        return "Update complete"

    # -------------------------
    # RETRIEVE
    # -------------------------
    async def retrieve(self, client_id, query, top_k):

        store = await self._load_store(client_id)

        if not store:
            return []

        try:
            return await asyncio.to_thread(
                store.similarity_search,
                query,
                top_k
            )
        except Exception:
            logger.exception("[CHROMA] Retrieval failed")
            return []