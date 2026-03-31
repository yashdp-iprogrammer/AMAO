import json
import time
import asyncio
from src.agents.base import BaseAgent
from src.prompts.nosql_prompt import NOSQL_PROMPT
from src.tools.nosql_search import run_nosql_query
from src.Database.connection_manager import ConnectionManager
from src.Database.schema_extractor.nosql_extractor import NoSQLSchemaExtractor


class NoSQLAgent(BaseAgent):

    def __init__(self, name, config, llm):
        super().__init__(name, config)

        self.llm = llm
        self.schema_extractor = NoSQLSchemaExtractor()

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

        nosql_connections = connections.get("nosql", {})

        schemas = {}

        for alias, conn_info in nosql_connections.items():

            cache_key = f"{client_id}_{alias}"

            cached = self._schema_cache.get(cache_key)

            if cached:
                age = time.time() - cached["timestamp"]

                if age < self._cache_ttl:
                    print(f"[NOSQL SCHEMA] Cache hit for nosql_{alias}")
                    schemas[alias] = cached["schema"]
                    continue
                else:
                    print(f"[SCHEMA] Cache expired for nosql_{alias}")


            print(f"[NOSQL SCHEMA] Cache miss for nosql_{alias}")

            schema = await self.schema_extractor.extract_schema(conn_info)

            # self._schema_cache[cache_key] = {
            #     "schema": schema,
            #     "timestamp": time.time()
            # }

            # schemas[alias] = {
            #     "db_type": conn_info["db_type"],
            #     "db_name": conn_info.get("db_name"),
            #     "schema": schema
            # }
            
            full_schema = {
                "db_type": conn_info["db_type"],
                "db_name": conn_info.get("db_name"),
                "schema": schema
            }

            self._schema_cache[cache_key] = {
                "schema": full_schema,
                "timestamp": time.time()
            }

            schemas[alias] = full_schema

        print("NoSQL schemas:\n", schemas)

        return schemas

    # -------------------------
    # Format schema
    # -------------------------
    def _format_schema(self, schemas):

        schema_text = ""

        for alias, schema in schemas.items():
            
            db_type = schema.get("db_type")

            schema_text += f"\nConnection: {alias}\n"
            schema_text += f"Database Type: {db_type}\n"


            for key, value in schema.items():

                schema_text += f"{key}: {value}\n"

        print("Formatted NoSQL schemas:\n",schema_text)
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

        prompt = NOSQL_PROMPT.format(
            schema=schema_text,
            user_id=state["user_id"],
            client_id=state["client_id"],
            query=state["user_query"]
        )

        response = await self.llm.ainvoke(prompt)
        raw = response.content.strip()

        print("LLM Response for NoSQL Query:", raw)

        try:
            parsed = json.loads(raw)

            if isinstance(parsed, dict):
                return [parsed]  # single query

            if isinstance(parsed, list):
                return parsed  # multiple queries

            return []

        except Exception as e:
            print("JSON Parse Error:", e)
            return []

    # -------------------------
    # Execute single query
    # -------------------------
    async def _execute_query(self, task, nosql_connections):
        
        alias = task.get("connection_alias")

        if not alias:
            return None

        conn_info = nosql_connections.get(alias)

        if not conn_info:
            print(f"Invalid connection alias: {alias}")
            return None

        try:
            rows = await run_nosql_query(task, conn_info)
        except Exception as e:
            print("NoSQL Execution Error:", e)
            return None

        return {
            "connection": alias,
            "query": task, 
            "rows": rows
        }


    # -------------------------
    # Main run
    # -------------------------
    async def run(self, state):

        tasks = await self._generate_sub_queries(state)
        
        print("Generated NoSQL tasks:", tasks)
        
        client_id = state["client_id"]
        current_user = state["current_user"]
        
        connection_manager = state["connection_manager"]

        connections = connection_manager.get_client_connections(
            client_id,
            current_user
        )

        nosql_connections = connections.get("nosql", {})

        print(f"[NOSQL AGENT] Total tasks: {len(tasks)}")

        coroutines = [
            self._execute_query(task, nosql_connections)
            for task in tasks
        ]

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        all_results = [
            r for r in results
            if r and not isinstance(r, Exception)
        ]

        existing = state.get("nosql_agent_results", [])

        return {
            "nosql_agent_results": existing + all_results
        }
