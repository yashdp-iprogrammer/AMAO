from typing import Optional, Dict
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    db_type: str
    host: str
    port: int
    username: str
    password: str
    db_name: str


class AgentConfig(BaseModel):
    model_name: str
    provider: str
    temperature: float = 0

    database: Optional[Dict[str, DatabaseConfig]] = None
    top_k: Optional[int] = None
    vector_db: Optional[str] = None
    

class AgentCreate(BaseModel):
    model_id: str
    agent_name: str
    token_limit: int


class AgentUpdate(BaseModel):
    model_id: Optional[str] = None
    agent_name: Optional[str] = None
    token_limit: Optional[int] = None
    is_disabled: Optional[bool] = None


class AgentRead(BaseModel):
    agent_id: str
    model_id: str
    agent_name: str
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