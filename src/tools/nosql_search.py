import json
from src.tools.nosql_executors.mongo_executor import run_mongo_query
from fastapi.encoders import jsonable_encoder
from bson import ObjectId

EXECUTOR_MAP = {
    "mongodb": run_mongo_query,
}


async def run_nosql_query(query: dict, conn_info):

    if not query:
        return {"error": "Empty query"}

    if not isinstance(query, dict):
        return {"error": "Query must be a JSON object"}

    if not conn_info:
        return {"error": "Connection not found"}

    db_type = conn_info["db_type"]
    connection = conn_info["connection"]

    executor = EXECUTOR_MAP.get(db_type)

    if not executor:
        return {"error": f"Unsupported DB {db_type}"}

    try:
        result = await executor(connection, query)
        return jsonable_encoder(result, custom_encoder={ObjectId: str})
    except Exception as e:
        return {"error": str(e)}