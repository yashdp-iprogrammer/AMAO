import os
import asyncio
from cachetools import TTLCache
from collections import defaultdict
from src.core.llm_providers.registry import get_providers
from src.utils.logger import logger


class LLMFactory():

    def __init__(self, runtime_manager):
        self.runtime_manager = runtime_manager
        self.providers = get_providers(runtime_manager)


        # -------------------------
        # SHARED CACHE (TTL + LRU)
        # -------------------------
        self._cache = TTLCache(maxsize=100, ttl=3600)

        # -------------------------
        # PER MODEL LOCKS
        # -------------------------
        self._locks = defaultdict(asyncio.Lock)
        

    async def create(self, llm_config: dict):

        model_name = llm_config["model_name"]
        provider = llm_config["provider"]
        temperature = llm_config.get("temperature", 0)
        api_key = llm_config.get("api_key")

        cache_key = (
            provider,
            model_name,
            temperature,
            api_key,
            llm_config.get("base_url")  # None for non-self-hosted
        )

        # -------------------------
        # FAST PATH (NO LOCK)
        # -------------------------
        cached = self._cache.get(cache_key)
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
        lock = self._locks[cache_key]

        async with lock:

            # -------------------------
            # DOUBLE CHECK
            # -------------------------
            cached = self._cache.get(cache_key)
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

            provider_instance = self.providers.get(provider)

            if not provider_instance:
                raise ValueError(f"Unsupported provider: {provider}")
            
            try:
                llm = await provider_instance.create(llm_config)

            except ValueError as ve:
                logger.error(f"[LLM FACTORY] Validation error | provider={provider} | error={str(ve)}")
                raise ValueError(f"{provider.upper()} ERROR: {str(ve)}") from ve

            except Exception as e:
                logger.exception("[LLM FACTORY] Unexpected failure")
                raise RuntimeError(f"Failed to initialize {provider} LLM")

            # -------------------------
            # CACHE STORE
            # -------------------------
            self._cache[cache_key] = llm

            logger.info(
                f"[LLM FACTORY] LLM initialized and cached | model={model_name}"
            )

            return llm