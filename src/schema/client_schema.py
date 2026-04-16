from sqlmodel import Field
from typing import Optional, Dict
from pydantic import BaseModel, EmailStr, field_validator
import re
from src.schema.agent_schema import AgentConfig

PHONE_REGEX = r"^\+?[1-9]\d{9,14}$"  # E.164 format


class ClientCreate(BaseModel):
    client_name: str = Field(min_length=2, max_length=100)
    client_email: EmailStr
    phone: str
    password: str = Field(min_length=8, max_length=128)
    allowed_agents: Dict[str, AgentConfig]

    @field_validator("phone")
    def validate_phone(cls, v):
        if not re.match(PHONE_REGEX, v):
            raise ValueError("Invalid phone number format")
        return v


class ClientUpdate(BaseModel):
    client_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    client_email: Optional[EmailStr] = None
    client_password:Optional[str] = None
    phone: Optional[str] = None
    allowed_agents: Optional[Dict[str, AgentConfig]] = None
    is_disabled: Optional[bool] = None

    @field_validator("phone")
    def validate_phone(cls, v):
        if v is not None and not re.match(PHONE_REGEX, v):
            raise ValueError("Invalid phone number format")
        return v


class ClientRead(BaseModel):
    client_id: str
    client_name: str
    client_email: EmailStr
    phone: str
    allowed_agents: Optional[Dict]
    is_disabled: bool

class ClientResponse(BaseModel):
    message: str
    client: ClientRead
    
    
class ClientResponseList(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    data: list[ClientRead]
