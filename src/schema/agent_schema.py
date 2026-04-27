from typing import Optional, Dict, Union, Literal
from pydantic import BaseModel, field_validator, model_validator


class BaseDBConfig(BaseModel):
    db_type: Literal["sqlite", "mysql", "postgres", "mssql", "mariadb", "mongo"]


class SQLiteConfig(BaseDBConfig):
    db_type: Literal["sqlite"]
    db_name: str

    @field_validator("db_name")
    @classmethod
    def validate_db_name(cls, v):
        if not v or not v.strip():
            raise ValueError("SQLite db_name cannot be empty")
        return v


class SQLDatabaseConfig(BaseDBConfig):
    db_type: Literal["mysql", "postgres", "mssql", "mariadb"]

    host: str
    port: int
    username: str
    password: str
    db_name: str

    @field_validator("host", "username", "password", "db_name")
    @classmethod
    def not_empty(cls, v):
        if not v or not str(v).strip():
            raise ValueError("Field cannot be empty")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if v <= 0 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class MongoConfig(BaseDBConfig):
    db_type: Literal["mongo"]

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    db_name: str

    @field_validator("host", "db_name")
    @classmethod
    def not_empty(cls, v):
        if not v or not str(v).strip():
            raise ValueError("Field cannot be empty")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if v <= 0 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


DatabaseConfig = Union[
    SQLiteConfig,
    SQLDatabaseConfig,
    MongoConfig
]


class AgentConfig(BaseModel):
    model_name: str
    provider: str
    api_key: Optional[str] = None
    temperature: float = 0

    database: Optional[Dict[str, DatabaseConfig]] = None

    top_k: Optional[int] = None
    vector_db: Optional[str] = None

    @field_validator("temperature")
    @classmethod
    def validate_temp(cls, v):
        if not (0 <= v <= 2):
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("top_k")
    @classmethod
    def validate_topk(cls, v):
        if v is not None and not (0 < v <= 20):
            raise ValueError("top_k must be greater than 0 and less than or equal to 20")
        return v

    @field_validator("vector_db")
    @classmethod
    def validate_vector_db(cls, v):
        if v is not None and v not in ["faiss", "chroma"]:
            raise ValueError("vector_db must be either 'faiss' or 'chroma'")
        return v
    
    @model_validator(mode="after")
    def validate_agent_config(self):

        if self.provider != "self_hosted" and not self.api_key:
            raise ValueError("API key required for non self-hosted providers")

        if self.database and (self.top_k or self.vector_db):
            raise ValueError("RAG and DB config cannot coexist")

        return self


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