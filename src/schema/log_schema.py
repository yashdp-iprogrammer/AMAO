from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class LogCreate(BaseModel):
    client_id: str
    user_id: str
    agent_id: str
    query: str
    response: str


class LogRead(BaseModel):
    log_id: str
    client_id: str
    user_id: str
    agent_id: str
    query: str
    response: str
    created_at: Optional[datetime]

