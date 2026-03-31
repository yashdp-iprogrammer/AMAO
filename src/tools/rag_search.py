from src.services.vector_db_service import VectorDBService

async def retrieve_documents(vectordb: VectorDBService, client_id: str , query: str , agent_config: dict):

    if not client_id:
        return []

    top_k = agent_config.get("top_k", 5)

    docs = vectordb.retrieve(
        client_id=client_id,
        query=query,
        top_k=top_k
    )

    if not docs:
        print("No docs found")
        return []

    print(f"[RAG] Retrieved {len(docs)} docs for client {client_id}")

    return [
        d.page_content if hasattr(d, "page_content") else str(d)
        for d in docs
    ]