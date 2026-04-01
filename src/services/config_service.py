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

    def __init__(self, session:AsyncSession, base_dir: str = "src/configs"):
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
        # Perform the creation action here
        client_dir = os.path.join(self.base_dir, f"client_id_{client_id}")
        os.makedirs(client_dir, exist_ok=True)
    
    
    def read_config(self, client_id: str):
        if client_id in self._config_cache:
            logger.info(f"Loaded config for client {client_id} from cache")
            return self._config_cache[client_id]

        config_path = self._get_client_config_path(client_id)
        
        try:
            with open(config_path, "r") as f:
                logger.info(f"Loaded config for client {client_id} from disk")
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Config file not found")


        self._config_cache[client_id] = config
        return config


    # def create_config(self, client_id: str, config: ClientConfigCreate):

    #     config_path = self._get_client_config_path(client_id)

    #     if os.path.exists(config_path):
    #         raise HTTPException(status_code=400, detail="Config file already exists")

    #     self._ensure_client_dir(client_id)

    #     config_dict = config.model_dump(exclude_none=True)

    #     with open(config_path, "w") as f:
    #         logger.info(f"Creating config for client {client_id}")
    #         yaml.safe_dump(config_dict, f, sort_keys=False)
            
    #     self._config_cache[client_id] = config_dict

    #     return {"message": "Config file created successfully"}
    

    async def create_config(self, client_id: str, config: ConfigCreate):

        config_path = self._get_client_config_path(client_id)

        # if os.path.exists(config_path):
        #     raise HTTPException(status_code=400, detail="Config file already exists")

        self._ensure_client_dir(client_id)

        agents_data = {}
        db_agents_data = {}

        for agent_name, agent in config.allowed_agents.items():

            agent_info = await self.agent_repo.get_agent_by_version(agent_name, agent.agent_version)
            if not agent_info:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid agent/version: {agent_name} ({agent.agent_version})"
                )
                
            model_info = await self.model_repo.get_model_by_id(agent_info.model_id)

            agent_dict = {
                "agent_id": agent_info.agent_id,
                "version": agent_info.agent_version,
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

            
        existing_client = await self.client_repo.get_client_by_id(client_id)
        if not existing_client:
            raise HTTPException(status_code=404, detail="Client not found")

        update_payload = ClientUpdate(allowed_agents=db_agents_data)
        await self.client_repo.update_client(existing_client, update_payload)
        
        with open(config_path, "w") as f:
            logger.info(f"Creating config for client {client_id}")
            yaml.safe_dump(config_dict, f, sort_keys=False)
        
        self._config_cache[client_id] = config_dict

        return {"message": "Config file created successfully"}

    
    # def update_config(self, client_id: str, config: ConfigUpdate):

    #     config_path = self._get_client_config_path(client_id)

    #     try:
    #         with open(config_path, "r") as f:
    #             logger.info(f"Updating config for client {client_id}")
    #             existing_config = yaml.safe_load(f) or {}
    #     except FileNotFoundError:
    #         raise HTTPException(status_code=404, detail="Config file not found")

    #     update_data = config.model_dump(exclude_none=True)

    #     existing_config.update(update_data)

    #     with open(config_path, "w") as f:
    #         yaml.safe_dump(existing_config, f, sort_keys=False)
            
    #     self._config_cache[client_id] = existing_config
    #     self._db_cache.pop(client_id, None)

    #     return {"message": "Config file updated successfully"}
    
    
    def remove_config(self, client_id: str):

        config_path = self._get_client_config_path(client_id)

        try:
            os.remove(config_path)
            logger.info(f"Deleting config for client {client_id}")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Config file not found")

        self._config_cache.pop(client_id, None)
        self._db_cache.pop(client_id, None)

        return {"message": "Config file removed successfully"}
