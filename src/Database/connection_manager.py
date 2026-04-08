from fastapi import HTTPException
from src.Database.connection_factory import ConnectionFactory
from src.utils.logger import logger
from src.schema.user_schema import CurrentUser
from src.services.config_service import ConfigService


class ConnectionManager:
    def __init__(self, config_service: ConfigService):
        self._connection_cache = {}
        self.config_service = config_service

    def get_client_connections(self, client_id: str, current_user: CurrentUser):

        if current_user.role_name == "SuperAdmin":
            pass

        elif current_user.role_name in ["Admin", "User"]:

            if client_id != current_user.client_id:
                logger.warning(f"[ConnectionManager] Unauthorized access attempt for client {client_id}")
                raise HTTPException(
                    status_code=403,
                    detail="You can only connect to your own client database"
                )

        else:
            logger.warning("[ConnectionManager] Unauthorized role access attempt")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized role"
            )

        # -------------------------
        # Cache check
        # -------------------------

        if client_id in self._connection_cache:
            logger.info(f"[ConnectionManager] Using cached connections for client {client_id}")
            return self._connection_cache[client_id]

        # -------------------------
        # Load client config
        # -------------------------

        config = self.config_service.read_config(client_id)

        allowed_agents = config.get("allowed_agents", {})

        client_connections = {
            "sql": {},
            "nosql": {}
        }

        # -------------------------
        # Loop through agents
        # -------------------------

        for agent_name, agent_config in allowed_agents.items():

            if not agent_config.get("enabled"):
                continue

            db_configs = agent_config.get("database")

            if not db_configs:
                continue

            for conn_alias, db_config in db_configs.items():

                try:
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
                    logger.exception(f"[ConnectionManager] Failed to create connection '{conn_alias}' for client {client_id}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create connection: {conn_alias}"
                    )

        # -------------------------
        # Cache connections
        # -------------------------

        self._connection_cache[client_id] = client_connections

        logger.info(f"[ConnectionManager] Created DB connections for client {client_id}")

        return client_connections