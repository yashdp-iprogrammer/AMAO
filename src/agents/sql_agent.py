import json
import asyncio
import time
from cachetools import TTLCache
from collections import defaultdict

from src.agents.base import BaseAgent
from src.prompts.sql_prompt import SQL_PROMPT
from src.tools.sql_search import run_sql_query
from src.Database.connection_manager import ConnectionManager
from src.Database.schema_extractor.sql_extractor import SQLSchemaExtractor
from src.utils.logger import logger
from langsmith import trace as langsmith_trace


class SQLAgent(BaseAgent):

    _schema_cache = TTLCache(maxsize=100, ttl=600)
    _client_locks = defaultdict(asyncio.Lock)

    def __init__(self, name, config, llm):
        super().__init__(name, config)
        self.llm = llm
        self.schema_extractor = SQLSchemaExtractor()

    async def _get_schemas(self, client_id, current_user, connection_manager: ConnectionManager):

        connections = await connection_manager.get_client_connections(
            client_id,
            current_user
        )

        sql_connections = connections.get("sql", {})
        schemas = {}

        for alias, conn_info in sql_connections.items():

            cache_key = f"{client_id}_{alias}"

            cached = self._schema_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[SQLAgent] Schema cache hit | alias={alias}")
                schemas[alias] = cached
                continue

            client_lock = self._client_locks[cache_key]

            async with client_lock:

                cached = self._schema_cache.get(cache_key)
                if cached is not None:
                    schemas[alias] = cached
                    continue

                start = time.perf_counter()

                schema = await self.schema_extractor.extract_schema(
                    conn_info["connection"]
                )

                self._schema_cache[cache_key] = schema

                logger.info(
                    f"[SQLAgent] Schema extracted | alias={alias} | "
                    f"time={time.perf_counter() - start:.2f}s"
                )

                schemas[alias] = schema

        return schemas

    def _format_schema(self, schemas):

        schema_text = ""

        for alias, tables in schemas.items():
            schema_text += f"\nConnection Alias: {alias}\n"

            for table, columns in tables.items():
                schema_text += f"\nTable: {table}\n"

                for col in columns:
                    schema_text += f"- {col['column_name']} ({col['type']})\n"

        return schema_text

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

        start = time.perf_counter()

        response = await self.llm.ainvoke(prompt)
        raw_output = response.content.strip()
        print("SQL LLM QUERY:\n", raw_output)

        logger.info(
            f"[SQLAgent] LLM response received | time={time.perf_counter() - start:.2f}s"
        )
        
        if raw_output.startswith("```"):
            raw_output = raw_output.strip("`").replace("json\n", "", 1).strip()

        try:
            parsed = json.loads(raw_output)

            if isinstance(parsed, dict):
                return [parsed]

            if isinstance(parsed, list):
                return parsed

            return []

        except Exception:
            logger.warning(f"[SQLAgent] Failed to parse LLM response:\n{raw_output}")
            return []

    async def _execute_query(self, task, sql_connections, original_query):

        alias = task.get("connection_alias")
        query = task.get("query")

        if not alias or not query:
            return None

        # minimal safety check
        q = query.strip().lower()
        if not q.startswith("select"):
            logger.warning(f"[SQLAgent] Unsafe query blocked: {query}")
            return None

        conn_info = sql_connections.get(alias)
        if not conn_info:
            return None

        with langsmith_trace(f"SQL Execution [{alias}]") as span:
            try:
                start = time.perf_counter()

                span.metadata["original_query"] = original_query
                span.metadata["query"] = query
                span.metadata["connection_alias"] = alias

                rows = await asyncio.wait_for(
                    run_sql_query(query, conn_info["connection"]),
                    timeout=10
                )
                
                rows = rows[:1000] if rows else []
                span.metadata["rows_preview"] = rows[:3]
                span.metadata["row_count"] = len(rows)
                span.metadata["execution_time"] = time.perf_counter() - start
                
                logger.info(
                    f"[SQLAgent] Query executed | alias={alias} | "
                    f"rows={len(rows)} | time={time.perf_counter() - start:.2f}s"
                )

            except asyncio.TimeoutError:
                logger.error(f"[SQLAgent] Query timeout | alias={alias}")
                span.metadata["timeout"] = True
                return None

            except Exception as e:
                logger.exception(f"[SQLAgent] SQL execution failed | alias={alias}")
                span.metadata["error"] = str(e)
                return None

        return {
            "connection": alias,
            "query": query,
            "rows": rows
        }

    async def run(self, state):

        tasks = await self._generate_sub_queries(state)

        if not tasks:
            return {"sql_agent_results": state.get("sql_agent_results", [])}

        client_id = state["client_id"]
        current_user = state["current_user"]
        connection_manager: ConnectionManager = state["connection_manager"]

        connections = await connection_manager.get_client_connections(
            client_id,
            current_user
        )

        sql_connections = connections.get("sql", {})

        results = await asyncio.gather(*[
            self._execute_query(task, sql_connections, state["user_query"])
            for task in tasks
        ])

        all_results = [r for r in results if r]

        existing_results = state.get("sql_agent_results", [])

        return {
            "sql_agent_results": existing_results + all_results
        }