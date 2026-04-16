from pydantic import BaseModel
from typing import Optional, Dict
from src.schema.agent_schema import AgentConfig 

class ConfigCreate(BaseModel):
    client_name: str
    allowed_agents: Dict[str, AgentConfig]
    

class ConfigUpdate(BaseModel):
    client_name: Optional[str] = None
    allowed_agents: Optional[Dict] = None