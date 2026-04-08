from src.agents.base import BaseAgent
from src.tools.rag_search import retrieve_documents
import json
from src.services.vector_db_service import VectorDBService
from src.prompts.rag_prompt import RAG_PROMPT
from src.utils.logger import logger


class RAGAgent(BaseAgent):

    def __init__(self, name, config, llm):
        super().__init__(name, config)
        self.llm = llm
        db_type = config.get("vector_db", "faiss")
        self.vectordb = VectorDBService(db_type)

    async def _extract_sub_intents(self, query: str):
        """
        Uses LLM to split multi-intent RAG queries into atomic semantic questions.
        Always returns a list.
        """

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

    async def run(self, state):

        query = state["user_query"]
        client_id = state["client_id"]

        sub_queries = await self._extract_sub_intents(query)

        logger.info(f"[RAGAgent] Processing {len(sub_queries)} sub-queries")

        all_docs = []

        for sub_query in sub_queries:

            docs = await retrieve_documents(
                vectordb=self.vectordb,
                client_id=client_id,
                query=sub_query,
                agent_config=self.config
            )

            all_docs.append({
                "query": sub_query,
                "documents": docs
            })

        existing_results = state.get("rag_agent_results", [])

        return {
            "rag_agent_results": existing_results + all_docs
        }