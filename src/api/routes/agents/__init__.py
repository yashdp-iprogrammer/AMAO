from fastapi import APIRouter, Depends, Query
from typing import Annotated, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.Database.base_db import Database
from src.schema.agent_schema import AgentCreate, AgentResponseList, AgentUpdate, AgentRead, AgentResponse
from src.services.agent_service import AgentService
from src.Database import system_db as db
from src.security.o_auth import auth_dependency
from src.utils.logger import logger

router = APIRouter(prefix="/agents", tags=["Agents"])


def get_agent_service(session: AsyncSession = Depends(db.get_session)) -> AgentService:
    return AgentService(session)

agent_session = Annotated[AgentService, Depends(get_agent_service)]


@router.post("/add-agent", response_model=AgentResponse)
async def create_agent(
    agent: AgentCreate,
    service: agent_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[CREATE_AGENT] user={current_user}, agent_name={agent.agent_name}{agent.agent_version}")
    return await service.create_agent(agent)


@router.put("/update-agent/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent: AgentUpdate,
    service: agent_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[UPDATE_AGENT] user={current_user}, agent_id={agent_id}")
    return await service.update_agent(agent_id, agent)


@router.delete("/remove-agent/{agent_id}")
async def delete_agent(
    agent_id: str,
    service: agent_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[DELETE_AGENT] user={current_user}, agent_id={agent_id}")
    return await service.delete_agent(agent_id)


@router.get("/list-agents", response_model=AgentResponseList)
async def get_all_agents(
    service: agent_session,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin", "User"]))
):
    logger.info(f"[LIST_AGENTS] user={current_user}, page={page}, size={size}")
    return await service.get_all_agents(page, size, current_user)


@router.get("/get-agent/{agent_id}", response_model=AgentRead)
async def get_agent_by_id(
    agent_id: str,
    service: agent_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin", "User"]))
):
    logger.info(f"[GET_AGENT] user={current_user}, agent_id={agent_id}")
    return await service.get_agent_by_id(agent_id, current_user)