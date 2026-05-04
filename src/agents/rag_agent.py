from src.agents.base import BaseAgent
from src.tools.rag_search import retrieve_documents
import json
from src.prompts.rag_prompt import RAG_PROMPT
from src.utils.logger import logger
from langsmith import trace as langsmith_trace
import time
import asyncio


class RAGAgent(BaseAgent):

    def __init__(self, name, config, llm):
        super().__init__(name, config)
        self.llm = llm

    async def _extract_sub_intents(self, query: str):

        prompt = RAG_PROMPT.format(query=query)

        response = await self.llm.ainvoke(prompt)

        logger.info("[RAGAgent] LLM response received for sub-intent extraction")

        try:
            sub_queries = json.loads(response.content.strip())

            if not isinstance(sub_queries, list):
                logger.warning("[RAGAgent] Unexpected sub-intent format, falling back to original query")
                return [query]

            return sub_queries

        except Exception:
            logger.warning("[RAGAgent] Failed to parse sub-intents, using original query")
            return [query]
        
    
    async def _retrieve_single(self, sub_query, query, client_id, vectordb):

        with langsmith_trace(f"RAG Retrieval [{sub_query}]") as span:
            try:
                start = time.perf_counter()

                span.metadata["original_query"] = query
                span.metadata["sub_query"] = sub_query

                docs = await asyncio.wait_for(
                    retrieve_documents(
                        vectordb=vectordb,
                        client_id=client_id,
                        query=sub_query,
                        agent_config=self.config
                    ),
                    timeout=10
                )

                span.metadata["num_docs"] = len(docs)
                span.metadata["doc_preview"] = [
                    (
                        getattr(doc, "page_content", None)
                        or (doc.get("page_content") if isinstance(doc, dict) else None)
                        or str(doc)
                    )[:100]
                    for doc in docs[:3]
                ] if docs else []
                span.metadata["execution_time"] = time.perf_counter() - start

                return {
                    "query": sub_query,
                    "documents": docs
                }

            except asyncio.TimeoutError:
                span.metadata["timeout"] = True
                logger.error(f"[RAGAgent] Timeout | sub_query='{sub_query}'")
                return None

            except Exception as e:
                logger.exception(f"[RAGAgent] Retrieval failed | sub_query='{sub_query}'")
                span.metadata["error"] = str(e)
                return None

    async def run(self, state):

        query = state["user_query"]
        client_id = state["client_id"]
        vectordb = state.get("vectordb")

        if not vectordb:
            raise ValueError("RAGAgent invoked but vectordb is not initialized")

        sub_queries = await self._extract_sub_intents(query)

        logger.info(f"[RAGAgent] Processing {len(sub_queries)} sub-queries")

        results = await asyncio.gather(*[
            self._retrieve_single(sub_query, query, client_id, vectordb)
            for sub_query in sub_queries
        ])

        all_docs = [r for r in results if r]
        
        if not all_docs:
            logger.warning(f"[RAGAgent] No documents retrieved for query='{query}'")

        existing_results = state.get("rag_agent_results", [])

        return {
            "rag_agent_results": existing_results + all_docs
        }