async def run_mongo_query(db, query):

    operation = query.get("operation")
    collection = query.get("collection")

    if operation == "find":

        cursor = db[collection].find(query.get("filter", {}))

        return await cursor.to_list(length=100)

    if operation == "aggregate":

        cursor = db[collection].aggregate(query.get("pipeline", []))

        return await cursor.to_list(length=100)

    return {"error": "Unsupported Mongo operation"}