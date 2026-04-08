from sqlalchemy import text
from src.utils.logger import logger


async def run_sql_query(query: str, connection):

    logger.info("[SQL SEARCH] Executing SQL query")

    async with connection.session_scope() as session:

        result = await session.execute(text(query))

        rows = result.fetchall()

        return [dict(row._mapping) for row in rows]