from pydantic import BaseModel
from typing import Optional, Dict
from src.schema.agent_schema import AgentVersion 

class ConfigCreate(BaseModel):
    client_name: str
    allowed_agents: Dict[str, AgentVersion]
    

class ConfigUpdate(BaseModel):
    client_name: Optional[str] = None
    allowed_agents: Optional[Dict] = None