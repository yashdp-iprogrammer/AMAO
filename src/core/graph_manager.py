import asyncio
from typing import Dict
from collections import defaultdict
from cachetools import TTLCache

from src.core.llm_factory import LLMFactory
from src.core.orchestrator import Orchestrator
from src.core.agent_factory import AgentFactory
from src.services.config_service import ConfigService
from src.utils.logger import logger


class GraphManager:

    # -------------------------
    # SHARED CACHE (TTL + LRU)
    # -------------------------
    _cache: TTLCache[str, Orchestrator] = TTLCache(maxsize=100, ttl=1800)

    # -------------------------
    # PER CLIENT LOCKS (AUTO-CREATED)
    # -------------------------
    _client_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def __init__(self):
        self._factory = AgentFactory()

    # -------------------------
    # GET ORCHESTRATOR
    # -------------------------
    async def get_orchestrator(self, client_id: str, config_service: ConfigService):

        # FAST CACHE CHECK (NO LOCK)
        cached = self._cache.get(client_id)
        if cached is not None:
            logger.info(f"[GRAPH MANAGER] Cache hit | client_id={client_id}")
            return cached

        logger.info(f"[GRAPH MANAGER] Cache miss | client_id={client_id}")

        # GET CLIENT LOCK (AUTO CREATED)
        client_lock = self._client_locks[client_id]

        # SINGLE-FLIGHT PER CLIENT
        async with client_lock:

            # DOUBLE CHECK AFTER LOCK
            cached = self._cache.get(client_id)
            if cached is not None:
                logger.info(f"[GRAPH MANAGER] Cache hit after lock | client_id={client_id}")
                return cached

            # -------------------------
            # BUILD ORCHESTRATOR
            # -------------------------
            logger.info(f"[GRAPH MANAGER] Creating orchestrator | client_id={client_id}")

            client_config = config_service.read_config(client_id)
            agent_configs = client_config.get("allowed_agents", {})

            if not agent_configs:
                logger.warning(f"[GRAPH MANAGER] No agents defined | client_id={client_id}")
                raise ValueError("No agents defined in config")

            enabled_configs = {
                name: conf for name, conf in agent_configs.items()
                if conf.get("enabled")
            }

            if not enabled_configs:
                logger.warning(f"[GRAPH MANAGER] No enabled agents found | client_id={client_id}")
                raise ValueError(f"No enabled agents found for client '{client_id}'")

            logger.info(
                f"[GRAPH MANAGER] Enabled agents loaded | count={len(enabled_configs)}, client_id={client_id}"
            )

            agents = await self._factory.create_agents(enabled_configs)

            first_enabled_config = next(iter(enabled_configs.values()))
            llm = await LLMFactory.create(first_enabled_config)

            orchestrator = Orchestrator(agents, llm)

            # CACHE WRITE
            self._cache[client_id] = orchestrator

            logger.info(f"[GRAPH MANAGER] Orchestrator created and cached | client_id={client_id}")

            return orchestrator

    # -------------------------
    # INVALIDATION
    # -------------------------
    async def invalidate(self, client_id: str):

        client_lock = self._client_locks[client_id]

        async with client_lock:

            self._cache.pop(client_id, None)
            self._client_locks.pop(client_id, None)

        logger.info(f"[GRAPH MANAGER] Cache invalidated | client_id={client_id}")