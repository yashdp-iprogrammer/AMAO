from src.core.registry import AgentRegistry
from src.core.llm_factory import LLMFactory


class AgentFactory:

    def __init__(self):
        self.registry = AgentRegistry()

    def create_agents(self, agent_configs: dict):

        agents = {}

        for agent_name, agent_conf in agent_configs.items():

            agent_cls = self.registry.get(agent_name)

            if not agent_cls:
                raise ValueError(f"Agent type '{agent_name}' not registered")

            llm = LLMFactory.create({
                "model_name": agent_conf["model_name"],
                "temperature": agent_conf.get("temperature", 0),
                "api_key": agent_conf.get("api_key")
            })

            agents[agent_name] = agent_cls(
                name=agent_name,
                config=agent_conf,
                llm=llm
            )

        return agents