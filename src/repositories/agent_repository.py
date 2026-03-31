from datetime import datetime, timezone
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from src.schema.agent_schema import AgentUpdate, AgentVersion
from src.Database.models import Agent


class AgentRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_agent(self, agent: Agent):
        self.session.add(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        return agent


    async def update_agent(self, existing_agent: Agent, agent:AgentUpdate):
        update_data = agent.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(existing_agent, key, value)
        existing_agent.updated_at = datetime.now(timezone.utc)

        self.session.add(existing_agent)
        await self.session.commit()
        await self.session.refresh(existing_agent)
        return existing_agent


    async def delete_agent(self, existing_agent: Agent):
        existing_agent.is_disabled = True
        existing_agent.updated_at = datetime.now(timezone.utc)

        self.session.add(existing_agent)
        await self.session.commit()


    async def get_agent_by_id(self, agent_id: str):
        statement = select(Agent).where(
            Agent.agent_id == agent_id,
            Agent.is_disabled == False
        )
        result = await self.session.exec(statement)
        return result.one_or_none()
    
    async def get_agent_by_version(self, agent_name: str, agent_version: str):
        statement = select(Agent).where(
            Agent.agent_name == agent_name,
            Agent.agent_version == agent_version,
            Agent.is_disabled == False
        )
        result = await self.session.exec(statement)
        return result.one_or_none()


    async def get_all_agents(self, page: int, size: int):

        statement = select(Agent).where(Agent.is_disabled == False)

        count_stmt = select(func.count()).select_from(statement.subquery())
        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        offset = (page - 1) * size
        
        statement = statement.offset(offset).limit(size)

        result = await self.session.exec(statement)
        agents = result.all()
        
        total_pages = (total + size - 1) // size

        return {
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "data": agents
        }