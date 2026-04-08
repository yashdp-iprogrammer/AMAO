import os
import yaml
from fastapi import HTTPException
from src.utils.logger import logger
from sqlmodel.ext.asyncio.session import AsyncSession
from src.schema.config_schema import ConfigCreate
from src.schema.client_schema import ClientUpdate
from src.repositories.agent_repository import AgentRepo
from src.repositories.model_repository import ModelRepo
from src.repositories.client_repository import ClientRepo

class ConfigService:

    def __init__(self, session: AsyncSession, base_dir: str = "src/configs"):
        self.session = session
        self.agent_repo = AgentRepo(session)
        self.model_repo = ModelRepo(session)
        self.client_repo = ClientRepo(session)
        self.base_dir = os.path.abspath(base_dir)
        self._config_cache = {}
        self._db_cache = {}
        
        
    def _get_client_config_path(self, client_id: str):
        return os.path.join(self.base_dir, f"client_id_{client_id}", "config.yaml")


    def _ensure_client_dir(self, client_id: str):
        client_dir = os.path.join(self.base_dir, f"client_id_{client_id}")
        os.makedirs(client_dir, exist_ok=True)


    def read_config(self, client_id: str):
        if client_id in self._config_cache:
            logger.info(f"[CONFIG] Cache hit for client {client_id}")
            return self._config_cache[client_id]

        config_path = self._get_client_config_path(client_id)

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
                logger.info(f"[CONFIG] Loaded config from disk for client {client_id}")
        except FileNotFoundError:
            logger.warning(f"[CONFIG] Config not found for client {client_id}")
            raise HTTPException(status_code=404, detail="Config file not found")

        self._config_cache[client_id] = config
        return config


    async def create_config(self, client_id: str, config: ConfigCreate):
        logger.info(f"[CONFIG] Creating config for client {client_id}")

        config_path = self._get_client_config_path(client_id)
        self._ensure_client_dir(client_id)

        agents_data = {}
        db_agents_data = {}

        for agent_name, agent in config.allowed_agents.items():

            logger.info(f"[CONFIG] Validating agent {agent_name}:{agent.agent_version}")

            agent_info = await self.agent_repo.get_agent_by_version(agent_name, agent.agent_version)

            if not agent_info:
                logger.warning(f"[CONFIG] Invalid agent/version: {agent_name}:{agent.agent_version}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid agent/version: {agent_name} ({agent.agent_version})"
                )

            model_info = await self.model_repo.get_model_by_id(agent_info.model_id)

            agent_dict = {
                "agent_id": agent_info.agent_id,
                "agent_version": agent_info.agent_version,
                "enabled": True,
                "model_name": model_info.model_name,
                "temperature": getattr(agent_info, "temperature", 0),
                "description": getattr(agent_info, "description", "")
            }

            if agent.database:
                agent_dict["database"] = {
                    k: v.model_dump(exclude_none=True)
                    for k, v in agent.database.items()
                }

            if agent.rag:
                rag_config = agent.rag.model_dump(exclude_none=True)
                agent_dict["top_k"] = rag_config.get("top_k", 3)
                agent_dict["vector_db"] = rag_config.get("vector_db", "faiss")

            agents_data[agent_name] = agent_dict
            db_agents_data[agent_name] = agent.model_dump(exclude_none=True)

        config_dict = {
            "client_name": config.client_name,
            "allowed_agents": agents_data
        }

        logger.info(f"[CONFIG] Validating client existence: {client_id}")

        existing_client = await self.client_repo.get_client_by_id(client_id)
        if not existing_client:
            logger.warning(f"[CONFIG] Client not found: {client_id}")
            raise HTTPException(status_code=404, detail="Client not found")

        update_payload = ClientUpdate(allowed_agents=db_agents_data)

        await self.client_repo.update_client(existing_client, update_payload)
        logger.info(f"[CONFIG] Updated allowed_agents in DB for client {client_id}")

        with open(config_path, "w") as f:
            yaml.safe_dump(config_dict, f, sort_keys=False)

        logger.info(f"[CONFIG] Config file created successfully for client {client_id}")

        self._config_cache[client_id] = config_dict

        return {"message": "Config file created successfully"}


    def remove_config(self, client_id: str):

        logger.info(f"[CONFIG] Removing config for client {client_id}")

        config_path = self._get_client_config_path(client_id)

        try:
            os.remove(config_path)
        except FileNotFoundError:
            logger.warning(f"[CONFIG] Config file not found for deletion: {client_id}")
            raise HTTPException(status_code=404, detail="Config file not found")

        self._config_cache.pop(client_id, None)
        self._db_cache.pop(client_id, None)

        logger.info(f"[CONFIG] Config removed successfully for client {client_id}")

        return {"message": "Config file removed successfully"}