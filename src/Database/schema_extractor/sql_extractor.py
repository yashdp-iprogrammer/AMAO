from sqlalchemy import inspect
from src.utils.logger import logger


class SQLSchemaExtractor:

    async def extract_schema(self, connection):

        engine = connection.engine

        logger.info("[SQLSchemaExtractor] Extracting schema")

        async with engine.connect() as conn:
            schema = await conn.run_sync(self._extract_sync)

        return schema

    def _extract_sync(self, sync_conn):

        inspector = inspect(sync_conn)

        schema = {}

        tables = inspector.get_table_names()

        for table in tables:

            columns = inspector.get_columns(table)

            schema[table] = [
                {
                    "column_name": col["name"],
                    "type": str(col["type"])
                }
                for col in columns
            ]

        return schema