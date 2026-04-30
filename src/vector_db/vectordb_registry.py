import json
import asyncio
from collections import defaultdict
from cachetools import TTLCache

from src.vector_db.faiss_store import FaissVectorStore
from src.vector_db.chroma_store import ChromaVectorStore
from src.vector_db.pinecone_store import PineconeVectorStore


SUPPORTED_VECTOR_STORES = {
    "faiss": FaissVectorStore,
    "chroma": ChromaVectorStore,
    "pinecone": PineconeVectorStore,
}

# -------------------------
# CACHE (TTL + LRU)
# -------------------------
_vector_store_cache = TTLCache(maxsize=50, ttl=1800)


# -------------------------
# PER-KEY LOCKS
# -------------------------
_locks = defaultdict(asyncio.Lock)


async def get_vector_store(client_id: str, db_type: str, db_config: dict = None):

    db_config = db_config or {}


    try:
        config_key = json.dumps(db_config, sort_keys=True)
    except Exception:
        config_key = "default"

    cache_key = f"{client_id}:{db_type}:{config_key}" if client_id else None


    cached = _vector_store_cache.get(cache_key)
    if cached is not None:
        return cached


    cls = SUPPORTED_VECTOR_STORES.get(db_type)
    if not cls:
        raise ValueError(f"Unsupported vector DB: {db_type}")

    # -------------------------
    # PER-KEY LOCK
    # -------------------------
    if cache_key:
        lock = _locks[cache_key]

        async with lock:

            # DOUBLE CHECK
            cached = _vector_store_cache.get(cache_key)
            if cached is not None:
                return cached


            if db_type == "faiss":
                instance = cls()
            else:
                instance = cls(db_config)


            _vector_store_cache[cache_key] = instance

            return instance


    return cls()



async def invalidate_vector_store(client_id: str):

    keys_to_delete = [
        key for key in _vector_store_cache
        if key.startswith(f"{client_id}:")
    ]

    for key in keys_to_delete:
        _vector_store_cache.pop(key, None)
        _locks.pop(key, None)