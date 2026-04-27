from typing import Optional, List
from src.schema.user_schema import CurrentUser
from src.core.graph_manager import GraphManager
from sqlmodel.ext.asyncio.session import AsyncSession
from src.services.vector_db_service import VectorDBService
from src.utils.document_processor import document_processor
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from src.services.config_service import ConfigService
from src.Database import system_db as db
from typing import Annotated
from src.Database.connection_manager import ConnectionManager 
from src.security.o_auth import auth_dependency
from src.utils.logger import logger



router = APIRouter(tags=["Chat"])


def get_config_service(session: AsyncSession = Depends(db.get_session)) -> ConfigService:
    return ConfigService(session)


config_session = Annotated[ConfigService, Depends(get_config_service)]


def get_connection_manager(
    config_service: ConfigService = Depends(get_config_service)
):
    return ConnectionManager(config_service)


@router.post("/chat")
async def run_chat(
    request: Request,
    config_service: config_session,
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    query: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    current_user: CurrentUser = Depends(auth_dependency.get_current_active_user),
):
    graph_manager = request.app.state.graph_manager

    client_id = current_user.client_id

    logger.info(f"[ChatRoute] Incoming chat request for client_id={client_id}")

    vectordb = None

    config = config_service.read_config_internal(client_id)

    if files:
        logger.info(f"[ChatRoute] Processing {len(files)} uploaded files")

        rag_config = config["allowed_agents"].get("rag_agent")
        
        if not (rag_config and rag_config.get("enabled")):
            logger.warning(f"RAG not enabled for client {client_id}, skipping indexing")
    
        else:

            vector_db_type = rag_config.get("vector_db", "faiss")

            vectordb = VectorDBService(vector_db_type)

            for file in files:

                document_name = file.filename

                text_chunks = await document_processor.process_file(
                    client_id,
                    vector_db_type,
                    document_name,
                    file
                )

                if text_chunks is None:
                    logger.info(f"[ChatRoute] Skipping already processed file: {document_name}")
                    continue

                if not text_chunks:
                    logger.warning(f"[ChatRoute] No chunks extracted from file: {document_name}")
                    continue

                await vectordb.append_to_store(
                    client_id,
                    document_name,
                    text_chunks
                )

    orchestrator = await graph_manager.get_orchestrator(client_id, config_service)

    state = {
        "user_id": current_user.user_id,
        "client_id": client_id,
        "current_user": current_user,
        "user_query": query,
        "connection_manager": connection_manager,
        "execution_trace": []
    }

    result = await orchestrator.run(state)

    result.pop("connection_manager", None)

    logger.info(f"[ChatRoute] Chat request completed for client_id={client_id}")

    return result