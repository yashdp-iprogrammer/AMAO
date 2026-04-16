import os
import yaml
import asyncio
import tempfile
from cachetools import TTLCache
from collections import defaultdict
from fastapi import HTTPException
from typing import Dict
from src.utils.logger import logger
from sqlmodel.ext.asyncio.session import AsyncSession
from src.schema.agent_schema import AgentConfig
from src.repositories.agent_repository import AgentRepo
from src.repositories.model_repository import ModelRepo
from src.repositories.client_repository import ClientRepo


class ConfigService:

    # -------------------------
    # CACHE
    # -------------------------
    _config_cache = TTLCache(maxsize=200, ttl=1800)

    # -------------------------
    # PER CLIENT LOCKS
    # -------------------------
    _client_locks = defaultdict(asyncio.Lock)

    def __init__(self, session: AsyncSession, base_dir: str = "src/configs"):
        self.session = session
        self.agent_repo = AgentRepo(session)
        self.model_repo = ModelRepo(session)
        self.client_repo = ClientRepo(session)
        self.base_dir = os.path.abspath(base_dir)

    def _get_client_config_path(self, client_id: str):
        return os.path.join(self.base_dir, f"client_id_{client_id}", "config.yaml")

    def _ensure_client_dir(self, client_id: str):
        os.makedirs(os.path.dirname(self._get_client_config_path(client_id)), exist_ok=True)

    # -------------------------
    # READ CONFIG
    # -------------------------
    def read_config(self, client_id: str):

        cached = self._config_cache.get(client_id)
        if cached:
            logger.info(f"[CONFIG] Cache hit | client_id={client_id}")
            return cached

        config_path = self._get_client_config_path(client_id)

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
                logger.info(f"[CONFIG] Loaded config from disk for client {client_id}")
        except FileNotFoundError:
            logger.warning(f"[CONFIG] Config not found for client {client_id}")
            raise HTTPException(status_code=404, detail="Config file not found")
        except Exception:
            logger.exception("[CONFIG] Failed to read config")
            raise HTTPException(status_code=500, detail="Failed to read config")

        self._config_cache[client_id] = config
        return config

    # -------------------------
    # ATOMIC WRITE HELPER
    # -------------------------
    def _atomic_write(self, file_path: str, data: dict):
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, dir=os.path.dirname(file_path)) as tmp:
                yaml.safe_dump(data, tmp, sort_keys=False)
                temp_path = tmp.name

            os.replace(temp_path, file_path)  # atomic replace
        except Exception:
            logger.exception("[CONFIG] Atomic write failed")
            raise

    # -------------------------
    # CREATE CONFIG
    # -------------------------
    async def create_config(self, client_id, client_name: str, allowed_agents: Dict[str, AgentConfig]):

        client_lock = self._client_locks[client_id]

        async with client_lock:

            logger.info(f"[CONFIG] Creating config | client_id={client_id}")

            config_path = self._get_client_config_path(client_id)
            self._ensure_client_dir(client_id)

            agents_data = {}

            for agent_name, agent in allowed_agents.items():

                agent_dict = {
                    "enabled": True,
                    "model_name": agent.model_name,
                    "temperature": agent.temperature,
                    "provider": agent.provider,
                }

                if agent.database:
                    agent_dict["database"] = {
                        k: v.model_dump(exclude_none=True)
                        for k, v in agent.database.items()
                    }

                if agent.top_k is not None:
                    agent_dict["top_k"] = agent.top_k

                if agent.vector_db is not None:
                    agent_dict["vector_db"] = agent.vector_db

                agents_data[agent_name] = agent_dict


            config_dict = {
                "client_name": client_name,
                "allowed_agents": agents_data
            }


            try:
                self._atomic_write(config_path, config_dict)
            except Exception:
                logger.critical("[CONFIG] DB updated but file write failed")
                raise HTTPException(status_code=500, detail="Config write failed")


            self._config_cache[client_id] = config_dict

            logger.info(f"[CONFIG] Config created successfully | client_id={client_id}")

            return {"message": "Config created successfully"}

    # -------------------------
    # DELETE CONFIG
    # -------------------------
    async def remove_config(self, client_id: str):

        client_lock = self._client_locks[client_id]

        async with client_lock:

            logger.info(f"[CONFIG] Removing config | client_id={client_id}")

            config_path = self._get_client_config_path(client_id)

            try:
                os.remove(config_path)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Config file not found")
            except Exception:
                logger.exception("[CONFIG] Failed to delete config")
                raise HTTPException(status_code=500, detail="Delete failed")

            self._config_cache.pop(client_id, None)

            logger.info(f"[CONFIG] Config removed | client_id={client_id}")

            return {"message": "Config removed successfully"}