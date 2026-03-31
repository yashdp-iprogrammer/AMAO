# from src.agents.base import BaseAgent
# from src.tools.rag_search import retrieve_documents


# class RAGAgent(BaseAgent):

#     def __init__(self, name, config, llm):
#         super().__init__(name, config)
#         self.llm = llm

#     async def run(self, state):

#         query = state.get("current_sub_query", state["user_query"])
#         client_id = state["client_id"]

#         docs = await retrieve_documents(
#             client_id=client_id,
#             query=query,
#             agent_config=self.config
#         )

#         existing_results = state.get("rag_results", [])

#         return {
#             "rag_results": existing_results + [
#                 {
#                     "query": query,
#                     "documents": docs
#                 }
#             ]
#         }




from src.agents.base import BaseAgent
from src.tools.rag_search import retrieve_documents
import json
import asyncio
from src.services.vector_db_service import VectorDBService
from src.prompts.rag_prompt import RAG_PROMPT


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

        try:
            sub_queries = json.loads(response.content.strip())
            if not isinstance(sub_queries, list):
                return [query]
            return sub_queries
        except Exception:
            return [query]



    # async def _retrieve_one(self, sub_query: str, client_id: str) -> dict:
    #     docs = await retrieve_documents(
    #         vectordb=self.vectordb,
    #         client_id=client_id,
    #         query=sub_query,
    #         agent_config=self.config
    #     )
    #     return {"query": sub_query, "documents": docs}

    # async def run(self, state) -> dict:
    #     query = state["user_query"]
    #     client_id = state["client_id"]

    #     sub_queries = await self._extract_sub_intents(query)

    #     # Run all retrievals in parallel
    #     results = await asyncio.gather(*[
    #         self._retrieve_one(sq, client_id) for sq in sub_queries
    #     ])

    #     existing = state.get("rag_results", [])
    #     return {"rag_results": existing + list(results)}
    
    async def run(self, state):

        query = state["user_query"]
        client_id = state["client_id"]

        sub_queries = await self._extract_sub_intents(query)
        print(sub_queries)

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
