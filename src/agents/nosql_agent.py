import json
import asyncio
import time
from cachetools import TTLCache
from collections import defaultdict

from src.agents.base import BaseAgent
from src.prompts.nosql_prompt import NOSQL_PROMPT
from src.tools.nosql_search import run_nosql_query
from src.Database.connection_manager import ConnectionManager
from src.Database.schema_extractor.nosql_extractor import NoSQLSchemaExtractor
from src.utils.logger import logger


class NoSQLAgent(BaseAgent):

    _schema_cache = TTLCache(maxsize=100, ttl=600)
    _client_locks = defaultdict(asyncio.Lock)

    def __init__(self, name, config, llm):
        super().__init__(name, config)
        self.llm = llm
        self.schema_extractor = NoSQLSchemaExtractor()

    async def _get_schemas(self, client_id, current_user, connection_manager: ConnectionManager):

        connections = await connection_manager.get_client_connections(
            client_id,
            current_user
        )

        nosql_connections = connections.get("nosql", {})
        schemas = {}

        for alias, conn_info in nosql_connections.items():

            cache_key = f"{client_id}_{alias}"

            cached = self._schema_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[NoSQLAgent] Schema cache hit | alias={alias}")
                schemas[alias] = cached
                continue

            client_lock = self._client_locks[cache_key]

            async with client_lock:

                cached = self._schema_cache.get(cache_key)
                if cached is not None:
                    schemas[alias] = cached
                    continue

                start = time.perf_counter()

                schema = await self.schema_extractor.extract_schema(conn_info)

                full_schema = {
                    "db_type": conn_info["db_type"],
                    "db_name": conn_info.get("db_name"),
                    "schema": schema
                }

                self._schema_cache[cache_key] = full_schema

                logger.info(
                    f"[NoSQLAgent] Schema extracted | alias={alias} | "
                    f"time={time.perf_counter() - start:.2f}s"
                )

                schemas[alias] = full_schema

        return schemas

    def _format_schema(self, schemas):

        schema_text = ""

        for alias, schema in schemas.items():

            schema_text += f"\nConnection: {alias}\n"
            schema_text += f"Database Type: {schema.get('db_type')}\n"

            for key, value in schema.items():
                schema_text += f"{key}: {value}\n"

        return schema_text

    async def _generate_sub_queries(self, state):

        schemas = await self._get_schemas(
            state["client_id"],
            state["current_user"],
            state["connection_manager"]
        )

        schema_text = self._format_schema(schemas)
        

        prompt = NOSQL_PROMPT.format(
            schema=schema_text,
            user_id=state["user_id"],
            client_id=state["client_id"],
            query=state["user_query"]
        )

        start = time.perf_counter()

        response = await self.llm.ainvoke(prompt)
        raw = response.content.strip()
        print("NOSQL LLM QUERY:\n", raw)

        logger.info(
            f"[NoSQLAgent] LLM response received | time={time.perf_counter() - start:.2f}s"
        )

        try:
            parsed = json.loads(raw)

            if isinstance(parsed, dict):
                return [parsed]

            if isinstance(parsed, list):
                return parsed

            return []

        except Exception:
            logger.warning(f"[NoSQLAgent] Failed to parse LLM response:\n{raw}")
            return []

    async def _execute_query(self, task, nosql_connections):

        alias = task.get("connection_alias")

        if not alias:
            return None

        conn_info = nosql_connections.get(alias)
        if not conn_info:
            return None

        try:
            start = time.perf_counter()

            rows = await asyncio.wait_for(
                run_nosql_query(task, conn_info),
                timeout=10
            )

            rows = rows[:1000] if rows else []

            logger.info(
                f"[NoSQLAgent] Query executed | alias={alias} | "
                f"rows={len(rows)} | time={time.perf_counter() - start:.2f}s"
            )

        except asyncio.TimeoutError:
            logger.error(f"[NoSQLAgent] Query timeout | alias={alias}")
            return None

        except Exception:
            logger.exception(f"[NoSQLAgent] NoSQL execution failed | alias={alias}")
            return None

        return {
            "connection": alias,
            "query": task,
            "rows": rows
        }

    async def run(self, state):

        tasks = await self._generate_sub_queries(state)

        if not tasks:
            return {"nosql_agent_results": state.get("nosql_agent_results", [])}

        client_id = state["client_id"]
        current_user = state["current_user"]
        connection_manager = state["connection_manager"]

        connections = await connection_manager.get_client_connections(
            client_id,
            current_user
        )

        nosql_connections = connections.get("nosql", {})

        results = await asyncio.gather(*[
            self._execute_query(task, nosql_connections)
            for task in tasks
        ])

        all_results = [r for r in results if r]

        existing = state.get("nosql_agent_results", [])

        return {
            "nosql_agent_results": existing + all_results
        }