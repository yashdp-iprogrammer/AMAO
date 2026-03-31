from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.agent_repository import AgentRepo
from src.Database.models import Agent
from src.schema.agent_schema import AgentCreate, AgentUpdate
from src.schema.user_schema import CurrentUser
from uuid import uuid4



class AgentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_repo = AgentRepo(session)

    async def create_agent(self, agent: AgentCreate):
        existing_agent = await self.agent_repo.get_agent_by_version(agent)
        if existing_agent:
            raise HTTPException(status_code=400, detail="Agent already exists")

        agent = Agent(
            agent_id=str(uuid4()),
            model_id=agent.model_id,
            agent_name=agent.agent_name,
            agent_version=agent.agent_version,
            token_limit=agent.token_limit,
            is_disabled=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        created_agent = await self.agent_repo.create_agent(agent)

        return {
            "message": "Agent created successfully",
            "agent": created_agent
        }


    async def update_agent(self, agent_id: str, agent: AgentUpdate):
        existing_agent = await self.agent_repo.get_agent_by_id(agent_id)

        if not existing_agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        updated_agent = await self.agent_repo.update_agent(existing_agent, agent)

        return {
            "message": "Agent updated successfully",
            "agent": updated_agent
        }


    async def delete_agent(self, agent_id: str):
        existing_agent = await self.agent_repo.get_agent_by_id(agent_id)

        if not existing_agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        await self.agent_repo.delete_agent(existing_agent)

        return {"message": "Agent deleted successfully"}


    async def get_all_agents(self, page: int, size: int, current_user: CurrentUser):
        return await self.agent_repo.get_all_agents(page, size)


    async def get_agent_by_id(self, agent_id: str, current_user: CurrentUser):
        agent = await self.agent_repo.get_agent_by_id(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        return agent