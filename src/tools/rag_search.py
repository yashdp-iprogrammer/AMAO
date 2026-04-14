from src.services.vector_db_service import VectorDBService
from src.utils.logger import logger


async def retrieve_documents(vectordb: VectorDBService, client_id: str, query: str, agent_config: dict):

    if not client_id:
        logger.warning("[RAG SEARCH] No client_id provided for document retrieval")
        return []

    top_k = agent_config.get("top_k", 5)

    logger.info(f"[RAG SEARCH] Retrieving documents | client_id={client_id}, top_k={top_k}")

    docs = await vectordb.retrieve(
        client_id=client_id,
        query=query,
        top_k=top_k
    )

    if not docs:
        logger.info(f"[RAG SEARCH] No documents found | client_id={client_id}")
        return []

    logger.info(f"[RAG SEARCH] Retrieved {len(docs)} documents | client_id={client_id}")

    return [
        d.page_content if hasattr(d, "page_content") else str(d)
        for d in docs
    ]