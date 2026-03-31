import asyncio
from typing import Dict
from src.core.llm_factory import LLMFactory
from src.core.orchestrator import Orchestrator
from src.core.agent_factory import AgentFactory
from src.services.config_service import ConfigService


class GraphManager:
    def __init__(self):
        self._factory = AgentFactory()
        self._cache: Dict[str, Orchestrator] = {}
        self._lock = asyncio.Lock()


    async def get_orchestrator(self, client_id: str, config_service: ConfigService):
        
        if client_id in self._cache:
            return self._cache[client_id]

        async with self._lock:
            
            if client_id in self._cache:
                return self._cache[client_id]

            client_config = config_service.read_config(client_id)
            agent_configs = client_config.get("allowed_agents", {})
            
            if not agent_configs:
                raise ValueError("No agents defined in config")
            
            enabled_configs = {
            name: conf for name, conf in agent_configs.items()
                if conf.get("enabled")
            }

            if not enabled_configs:
                raise ValueError(f"No enabled agents found for client '{client_id}'")

            
            agents = self._factory.create_agents(enabled_configs)
            
            # print("config values: ", agent_configs.values())

            first_enabled_config = next(iter(enabled_configs.values()))

            llm = LLMFactory.create(first_enabled_config)

            orchestrator = Orchestrator(agents, llm)
            orchestrator.build_graph()

            self._cache[client_id] = orchestrator

            return orchestrator