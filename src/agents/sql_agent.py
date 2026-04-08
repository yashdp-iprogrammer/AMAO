import json
import time
import asyncio
from src.agents.base import BaseAgent
from src.prompts.sql_prompt import SQL_PROMPT
from src.tools.sql_search import run_sql_query
from src.Database.connection_manager import ConnectionManager
from src.Database.schema_extractor.sql_extractor import SQLSchemaExtractor
from src.utils.logger import logger


class SQLAgent(BaseAgent):

    def __init__(self, name, config, llm):
        super().__init__(name, config)

        self.llm = llm
        self.schema_extractor = SQLSchemaExtractor()

        self._schema_cache = {}
        self._cache_ttl = 600

    # -------------------------
    # Get schemas
    # -------------------------
    async def _get_schemas(self, client_id, current_user, connection_manager: ConnectionManager):

        connections = connection_manager.get_client_connections(
            client_id,
            current_user
        )

        sql_connections = connections.get("sql", {})
        schemas = {}

        for alias, conn_info in sql_connections.items():

            cache_key = f"{client_id}_{alias}"
            cached = self._schema_cache.get(cache_key)

            if cached:
                age = time.time() - cached["timestamp"]

                if age < self._cache_ttl:
                    logger.info(f"[SQLAgent] Schema cache hit for connection: {alias}")
                    schemas[alias] = cached["schema"]
                    continue
                else:
                    logger.info(f"[SQLAgent] Schema cache expired for connection: {alias}")

            logger.info(f"[SQLAgent] Fetching schema for connection: {alias}")

            schema = await self.schema_extractor.extract_schema(
                conn_info["connection"]
            )

            self._schema_cache[cache_key] = {
                "schema": schema,
                "timestamp": time.time()
            }

            schemas[alias] = schema

        return schemas

    # -------------------------
    # Format schema
    # -------------------------
    def _format_schema(self, schemas):

        schema_text = ""

        for alias, tables in schemas.items():

            schema_text += f"\nConnection Alias: {alias}\n"

            for table, columns in tables.items():

                schema_text += f"\nTable: {table}\n"

                for col in columns:
                    schema_text += f"- {col['column_name']} ({col['type']})\n"

        return schema_text

    # -------------------------
    # Generate queries
    # -------------------------
    async def _generate_sub_queries(self, state):

        schemas = await self._get_schemas(
            state["client_id"],
            state["current_user"],
            state["connection_manager"]
        )

        schema_text = self._format_schema(schemas)

        prompt = SQL_PROMPT.format(
            schema=schema_text,
            user_id=state["user_id"],
            client_id=state["client_id"],
            query=state["user_query"]
        )

        response = await self.llm.ainvoke(prompt)
        raw_output = response.content.strip()

        logger.info(f"[SQLAgent] LLM response received for query generation:\n{raw_output}")

        try:
            parsed = json.loads(raw_output)
            return parsed

        except Exception:
            logger.warning("[SQLAgent] Failed to parse LLM response")
            return []

    # -------------------------
    # Execute single query
    # -------------------------
    async def _execute_query(self, task, sql_connections):

        alias = task.get("connection_alias")
        query = task.get("query")

        if not alias or not query:
            logger.warning("[SQLAgent] Missing alias or query in task")
            return None

        if not query.lower().startswith("select"):
            logger.warning(f"[SQLAgent] Non-SELECT query blocked for connection: {alias}")
            return None

        conn_info = sql_connections.get(alias)

        if not conn_info:
            logger.warning(f"[SQLAgent] Invalid connection alias: {alias}")
            return None

        try:
            rows = await run_sql_query(query, conn_info["connection"])
        except Exception:
            logger.exception(f"[SQLAgent] SQL execution failed for connection: {alias}")
            rows = []

        return {
            "connection": alias,
            "query": query,
            "rows": rows
        }

    # -------------------------
    # Main run
    # -------------------------
    async def run(self, state):

        tasks = await self._generate_sub_queries(state)

        logger.info(f"[SQLAgent] Generated {len(tasks)} SQL tasks")

        client_id = state["client_id"]
        current_user = state["current_user"]

        connection_manager: ConnectionManager = state["connection_manager"]

        connections = connection_manager.get_client_connections(
            client_id,
            current_user
        )

        sql_connections = connections.get("sql", {})

        coroutines = [
            self._execute_query(task, sql_connections)
            for task in tasks
        ]

        results = await asyncio.gather(*coroutines)

        all_results = [r for r in results if r]

        existing_results = state.get("sql_agent_results", [])

        return {
            "sql_agent_results": existing_results + all_results
        }