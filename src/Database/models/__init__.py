from typing import Optional, List, Dict
from datetime import datetime, timezone

from sqlmodel import SQLModel, Field, Column, DateTime, func, JSON, Relationship
from sqlalchemy import JSON


class Client(SQLModel, table=True):
    __tablename__ = "clients"

    client_id: str = Field(primary_key=True)
    client_name: str
    client_email: str
    phone: str
    password: str
    allowed_agents: Optional[Dict] = Field(default=None, sa_column=Column(JSON))
    is_disabled: bool = False
    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )
    
    users: List["User"] = Relationship(back_populates="client")
    logs: List["Log"] = Relationship(back_populates="client")


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    role_id: int = Field(primary_key=True, index=True)
    role_name: str = Field(nullable=False, unique=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True), onupdate=func.now()))
    
    # Relationships
    users: List["User"] = Relationship(back_populates="role")
    

class User(SQLModel, table=True):
    __tablename__ = "users"
    user_id: str = Field(primary_key=True, index=True)
    client_id: str = Field(foreign_key="clients.client_id", nullable=False)
    
    # NEW: Role Foreign Key
    role_id: int = Field(foreign_key="roles.role_id", nullable=False)
    
    user_name: str = Field(index=True, nullable=False)
    user_mobile: str = Field(nullable=True)
    user_email: str = Field(index=True, nullable=False, unique=True)
    user_password: str # Hashed
    is_disabled: bool = Field(default=False)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True), onupdate=func.now()))
 
    # Relationships
    client: "Client" = Relationship(back_populates="users")
    role: Role = Relationship(back_populates="users")
    logs: List["Log"] = Relationship(back_populates="user")


class Agent(SQLModel, table=True):
    __tablename__ = "agents"

    agent_id: str = Field(primary_key=True)
    model_id: str = Field(foreign_key="models.model_id")

    agent_name: str = Field(unique=True)
    token_limit: int
    is_disabled: bool = False
    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )

    model: Optional["Model"] = Relationship(back_populates="agents")
    logs: List["Log"] = Relationship(back_populates="agent")


class Model(SQLModel, table=True):
    __tablename__ = "models"

    model_id: str = Field(primary_key=True)
    model_name: str = Field(index=True, unique=True)
    provider: str = Field(max_length=35, index=True)
    token_size: int
    model_subscription: bool
    subscription_cost: float
    is_disabled: bool = Field(default=False)
    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )

    agents: List["Agent"] = Relationship(back_populates="model")


class Log(SQLModel, table=True):
    __tablename__ = "logs"

    log_id: str = Field(primary_key=True)
    client_id: str = Field(foreign_key="clients.client_id")
    user_id: str = Field(foreign_key="users.user_id")
    agent_id: str = Field(foreign_key="agents.agent_id")

    query: str
    response: str
    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )

    client: Optional["Client"] = Relationship(back_populates="logs")
    user: Optional["User"] = Relationship(back_populates="logs")
    agent: Optional["Agent"] = Relationship(back_populates="logs")
    feedback: Optional["Feedback"] = Relationship(back_populates="log")


class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"

    feedback_id: str = Field(primary_key=True)
    log_id: str = Field(foreign_key="logs.log_id")

    feedback: bool
    is_disabled: bool = Field(default=False)
    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )

    log: Optional["Log"] = Relationship(back_populates="feedback")
