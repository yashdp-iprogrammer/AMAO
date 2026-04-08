from src.utils.logger import logger

async def run_mongo_query(db, query):

    operation = query.get("operation")
    collection = query.get("collection")

    logger.info(f"[MONGO] Query execution | operation={operation}, collection={collection}")

    if operation == "find":

        cursor = db[collection].find(query.get("filter", {}))
        result = await cursor.to_list(length=100)

        logger.info(f"[MONGO] Find completed | collection={collection}, count={len(result)}")
        return result

    if operation == "aggregate":

        cursor = db[collection].aggregate(query.get("pipeline", []))
        result = await cursor.to_list(length=100)

        logger.info(f"[MONGO] Aggregate completed | collection={collection}, count={len(result)}")
        return result

    logger.warning(f"[MONGO] Unsupported Mongo operation: {operation}")
    return {"error": "Unsupported Mongo operation"}