from typing import Dict, Type
from src.agents.sql_agent import SQLAgent
from src.agents.rag_agent import RAGAgent
from src.agents.nosql_agent import NoSQLAgent

class AgentRegistry:

    def __init__(self):
        self._registry: Dict[str, Type] = {}
        self._register_builtin_agents()

    
    def _register_builtin_agents(self):
        self.register("sql_agent", SQLAgent)
        self.register("rag_agent", RAGAgent)
        self.register("nosql_agent", NoSQLAgent)

   
    def register(self, agent_type: str, agent_cls: Type):
        if agent_type in self._registry:    
            raise ValueError(f"Agent '{agent_type}' already registered")

        self._registry[agent_type] = agent_cls

    
    def get(self, agent_type: str):

        if agent_type not in self._registry:
            raise ValueError(
                f"Agent type '{agent_type}' not registered. "
                f"Available: {list(self._registry.keys())}"
            )

        return self._registry[agent_type]


    def list_types(self):
        return list(self._registry.keys())
