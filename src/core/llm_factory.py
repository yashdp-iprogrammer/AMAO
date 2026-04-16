import os
import asyncio
from cachetools import TTLCache
from collections import defaultdict

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from src.utils.logger import logger


class LLMFactory:

    # -------------------------
    # SHARED CACHE (TTL + LRU)
    # -------------------------
    _cache = TTLCache(maxsize=100, ttl=3600)

    # -------------------------
    # PER MODEL LOCKS
    # -------------------------
    _locks = defaultdict(asyncio.Lock)

    @classmethod
    async def create(cls, llm_config: dict):

        model_name = llm_config["model_name"]
        provider = llm_config["provider"]
        temperature = llm_config.get("temperature", 0)
        api_key = llm_config.get("api_key") or os.getenv("LLM_API_KEY")

        cache_key = (model_name, temperature, api_key)

        # -------------------------
        # FAST PATH (NO LOCK)
        # -------------------------
        cached = cls._cache.get(cache_key)
        if cached is not None:
            logger.info(
                f"[LLM FACTORY] Cache hit | model={model_name}, temperature={temperature}"
            )
            return cached

        logger.info(
            f"[LLM FACTORY] Cache miss | model={model_name}, temperature={temperature}"
        )

        # -------------------------
        # PER-KEY LOCK
        # -------------------------
        lock = cls._locks[cache_key]

        async with lock:

            # -------------------------
            # DOUBLE CHECK
            # -------------------------
            cached = cls._cache.get(cache_key)
            if cached is not None:
                logger.info(
                    f"[LLM FACTORY] Cache hit after lock | model={model_name}"
                )
                return cached

            # -------------------------
            # CREATE LLM
            # -------------------------
            logger.info(
                f"[LLM FACTORY] Initializing LLM | model={model_name}, temperature={temperature}"
            )

            try:
                if provider == "openai":
                    llm = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        api_key=api_key
                    )

                elif provider == "groq":
                    llm = ChatGroq(
                        model=model_name,
                        temperature=temperature,
                        api_key=api_key
                    )

                else:
                    logger.warning(f"[LLM FACTORY] Unsupported model: {model_name}")
                    raise ValueError(f"Unsupported model: {model_name}")

            except Exception:
                logger.exception("[LLM FACTORY] Failed to initialize LLM")
                raise

            # -------------------------
            # CACHE STORE
            # -------------------------
            cls._cache[cache_key] = llm

            logger.info(
                f"[LLM FACTORY] LLM initialized and cached | model={model_name}"
            )

            return llm