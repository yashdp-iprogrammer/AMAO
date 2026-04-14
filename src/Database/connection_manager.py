from fastapi import HTTPException
from cachetools import TTLCache
from collections import defaultdict
import asyncio

from src.Database.connection_factory import ConnectionFactory
from src.utils.logger import logger
from src.schema.user_schema import CurrentUser
from src.services.config_service import ConfigService


class ConnectionManager:

    # -------------------------
    # SHARED CACHE (TTL + LRU)
    # -------------------------
    _connection_cache = TTLCache(maxsize=100, ttl=1800)

    # -------------------------
    # PER CLIENT LOCKS
    # -------------------------
    _client_locks = defaultdict(asyncio.Lock)

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

    # -------------------------
    # GET CONNECTIONS
    # -------------------------
    async def get_client_connections(self, client_id: str, current_user: CurrentUser):

        if current_user.role_name == "SuperAdmin":
            pass

        elif current_user.role_name in ["Admin", "User"]:
            if client_id != current_user.client_id:
                logger.warning(f"[ConnectionManager] Unauthorized access | client_id={client_id}")
                raise HTTPException(
                    status_code=403,
                    detail="You can only connect to your own client database"
                )
        else:
            logger.warning("[ConnectionManager] Invalid role access attempt")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized role"
            )

        # -------------------------
        # FAST CACHE CHECK
        # -------------------------
        cached = self._connection_cache.get(client_id)
        if cached:
            logger.info(f"[ConnectionManager] Cache hit | client_id={client_id}")
            return cached

        logger.info(f"[ConnectionManager] Cache miss | client_id={client_id}")

        
        client_lock = self._client_locks[client_id]

        async with client_lock:

            # -------------------------
            # DOUBLE CHECK CACHE
            # -------------------------
            cached = self._connection_cache.get(client_id)
            if cached:
                logger.info(f"[ConnectionManager] Cache hit after lock | client_id={client_id}")
                return cached

            # -------------------------
            # LOAD CONFIG
            # -------------------------
            try:
                config = self.config_service.read_config(client_id)
            except Exception:
                logger.exception("[ConnectionManager] Failed to load config")
                raise

            allowed_agents = config.get("allowed_agents", {})

            if not allowed_agents:
                logger.warning(f"[ConnectionManager] No agents found | client_id={client_id}")
                raise HTTPException(
                    status_code=400,
                    detail="No agents configured for this client"
                )

            # -------------------------
            # BUILD CONNECTIONS
            # -------------------------
            client_connections = {
                "sql": {},
                "nosql": {}
            }

            try:
                for agent_name, agent_config in allowed_agents.items():

                    if not agent_config.get("enabled"):
                        continue

                    db_configs = agent_config.get("database")
                    if not db_configs:
                        continue

                    for conn_alias, db_config in db_configs.items():

                        conn = ConnectionFactory.create_connection(db_config)

                        conn_info = {
                            "connection": conn,
                            "db_name": db_config.get("db_name"),
                            "db_type": db_config.get("db_type")
                        }

                        if agent_name == "sql_agent":
                            client_connections["sql"][conn_alias] = conn_info

                        elif agent_name == "nosql_agent":
                            client_connections["nosql"][conn_alias] = conn_info

            except Exception:
                logger.exception(f"[ConnectionManager] Connection creation failed | client_id={client_id}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to initialize database connections"
                )

            # -------------------------
            # CACHE WRITE (SAFE)
            # -------------------------
            self._connection_cache[client_id] = client_connections

            logger.info(f"[ConnectionManager] Connections created | client_id={client_id}")

            return client_connections