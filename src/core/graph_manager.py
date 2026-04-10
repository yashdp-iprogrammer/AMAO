import asyncio
from typing import Dict
from src.core.llm_factory import LLMFactory
from src.core.orchestrator import Orchestrator
from src.core.agent_factory import AgentFactory
from src.services.config_service import ConfigService
from src.utils.logger import logger


class GraphManager:
    def __init__(self):
        self._factory = AgentFactory()
        self._cache: Dict[str, Orchestrator] = {}
        self._lock = asyncio.Lock()


    async def get_orchestrator(self, client_id: str, config_service: ConfigService):
        
        if client_id in self._cache:
            logger.info(f"[GRAPH MANAGER] Orchestrator cache hit | client_id={client_id}")
            return self._cache[client_id]

        logger.info(f"[GRAPH MANAGER] Orchestrator cache miss | client_id={client_id}")

        async with self._lock:
            
            if client_id in self._cache:
                logger.info(f"[GRAPH MANAGER] Orchestrator cache hit after lock | client_id={client_id}")
                return self._cache[client_id]

            logger.info(f"[GRAPH MANAGER] Creating orchestrator | client_id={client_id}")

            client_config = config_service.read_config(client_id)
            agent_configs = client_config.get("allowed_agents", {})
            
            if not agent_configs:
                logger.warning(f"[GRAPH MANAGER] No agents defined in config | client_id={client_id}")
                raise ValueError("No agents defined in config")
            
            enabled_configs = {
                name: conf for name, conf in agent_configs.items()
                if conf.get("enabled")
            }

            if not enabled_configs:
                logger.warning(f"[GRAPH MANAGER] No enabled agents found | client_id={client_id}")
                raise ValueError(f"No enabled agents found for client '{client_id}'")

            logger.info(f"[GRAPH MANAGER] Enabled agents loaded | count={len(enabled_configs)}, client_id={client_id}")

            agents = self._factory.create_agents(enabled_configs)

            first_enabled_config = next(iter(enabled_configs.values()))
            llm = LLMFactory.create(first_enabled_config)

            orchestrator = Orchestrator(agents, llm)

            self._cache[client_id] = orchestrator

            logger.info(f"[GRAPH MANAGER] Orchestrator created and cached | client_id={client_id}")

            return orchestrator