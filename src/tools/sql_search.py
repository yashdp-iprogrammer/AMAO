# from sqlalchemy import text
# from src.Database import Database


# async def run_sql_query(query: str):

#     if not query:
#         return {"error": "Empty query"}

#     query_clean = query.strip().lower()

#     if not query_clean.startswith("select"):
#         return {"error": "Only SELECT queries are allowed"}

#     # Optional stronger protection
#     forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]
#     if any(word in query_clean for word in forbidden):
#         return {"error": "Dangerous SQL detected"}

#     async with db.session_scope() as session:
#         try:
#             result = await session.exec(text(query))
#             rows = result.mappings().all()
#             return rows

#         except Exception as e:
#             return {"error": str(e)}



from sqlalchemy import text


async def run_sql_query(query: str, connection):

    async with connection.session_scope() as session:

        result = await session.execute(text(query))

        rows = result.fetchall()

        return [dict(row._mapping) for row in rows]