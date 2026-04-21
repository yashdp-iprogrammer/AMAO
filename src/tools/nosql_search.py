from src.tools.nosql_executors.mongo_executor import run_mongo_query
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from src.utils.logger import logger

EXECUTOR_MAP = {
    "mongo": run_mongo_query,
}


async def run_nosql_query(query: dict, conn_info):

    if not query:
        logger.warning("[NO_SQL SEARCH] Empty NoSQL query received")
        return {"error": "Empty query"}

    if not isinstance(query, dict):
        logger.warning("[NO_SQL SEARCH] Invalid NoSQL query format (not a dict)")
        return {"error": "Query must be a JSON object"}

    if not conn_info:
        logger.warning("[NO_SQL SEARCH] Missing connection info for NoSQL query")
        return {"error": "Connection not found"}

    db_type = conn_info["db_type"]
    connection = conn_info["connection"]

    executor = EXECUTOR_MAP.get(db_type)

    if not executor:
        logger.warning(f"[NO_SQL SEARCH] Unsupported NoSQL DB type: {db_type}")
        return {"error": f"Unsupported DB {db_type}"}

    logger.info(f"[NO_SQL SEARCH] Executing NoSQL query | db_type={db_type}")

    try:
        result = await executor(connection, query)

        logger.info(f"[NO_SQL SEARCH] NoSQL query executed successfully | db_type={db_type}")

        return jsonable_encoder(result, custom_encoder={ObjectId: str})

    except Exception:
        logger.exception(f"[NO_SQL SEARCH] Error executing NoSQL query | db_type={db_type}")
        return {"error": "Query execution failed"}