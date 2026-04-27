from src.core.registry import AgentRegistry
from src.core.llm_factory import LLMFactory
from src.utils.logger import logger


class AgentFactory:

    def __init__(self, llm_factory):
        self.registry = AgentRegistry()
        self.llm_factory = llm_factory

    async def create_agents(self, agent_configs: dict):

        logger.info(f"[AGENT FACTORY] Creating agents | count={len(agent_configs)}")

        agents = {}

        for agent_name, agent_conf in agent_configs.items():

            agent_cls = self.registry.get(agent_name)

            if not agent_cls:
                logger.warning(f"[AGENT FACTORY] Agent not registered: {agent_name}")
                raise ValueError(f"Agent type '{agent_name}' not registered")

            logger.info(f"[AGENT FACTORY] Initializing agent: {agent_name}")

            llm = await self.llm_factory.create({
                "model_name": agent_conf["model_name"],
                "provider": agent_conf["provider"],
                "temperature": agent_conf.get("temperature", 0),
                "api_key": agent_conf.get("api_key")
            })

            agents[agent_name] = agent_cls(
                name=agent_name,
                config=agent_conf,
                llm=llm
            )

        logger.info("[AGENT FACTORY] Agent creation completed")

        return agents