from typing import Optional, Dict
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    db_type: str
    host: str
    port: int
    username: str
    password: str
    db_name: str

class RAGConfig(BaseModel):
    top_k: int
    vector_db: str
    

class AgentCreate(BaseModel):
    model_id: str
    agent_name: str
    agent_version: str
    token_limit: int
    
class AgentVersion(BaseModel):
    agent_name: str
    agent_version: str
    
    # Optional configs
    database: Optional[Dict[str, DatabaseConfig]] = None
    rag: Optional[RAGConfig] = None


class AgentUpdate(BaseModel):
    model_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_version: Optional[str] = None
    token_limit: Optional[int] = None
    is_disabled: Optional[bool] = None


class AgentRead(BaseModel):
    agent_id: str
    model_id: str
    agent_name: str
    agent_version: str
    token_limit: int
    is_disabled: bool

class AgentResponse(BaseModel):
    message: str
    agent: AgentRead
    

class AgentResponseList(BaseModel):
    total: int
    page: int
    size: int
    data: list[AgentRead]