import time
from fastapi import FastAPI, Request, HTTPException
from src.Database import system_db as db
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.utils.db_seeder import seed_initial_data
from src.utils.logger import logger
from fastapi.responses import JSONResponse
from src.core.llm_factory_utils.port_allocator import PortAllocator
from src.core.llm_factory_utils.runtime_manager import VLLMRuntimeManager
from src.core.llm_factory import LLMFactory
from src.core.graph_manager import GraphManager
from src.services.config_service import ConfigService
from src.vector_db.base import BaseVectorStore

from src.api.routes.auth import router as auth
from src.api.routes.chat import router as chat
from src.api.routes.clients import router as client
from src.api.routes.user import router as user
from src.api.routes.feedback import router as feedback
from src.api.routes.agents import router as agent
from src.api.routes.models import router as model
from src.api.routes.logs import router as logs
from src.api.routes.config import router as config
import os

@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.port_allocator = PortAllocator(8005)
    runtime_manager = VLLMRuntimeManager(app.state.port_allocator)
    llm_factory = LLMFactory(runtime_manager)
    app.state.graph_manager = GraphManager(llm_factory)
    
    await db.init_db(db.engine)
    
    async with db.async_session() as session:
        await seed_initial_data(session)
        
        # SINGLE-CLIENT PRE-WARMING
        target_client_id = os.getenv("DEPLOYMENT_CLIENT_ID")
        
        if target_client_id:
            logger.info(f"PRE-WARMING: Booting Graph for Client: {target_client_id}")
            config_service = ConfigService(session)
            try:
                BaseVectorStore.warmup_embedding()
                await app.state.graph_manager.get_orchestrator(target_client_id, config_service)
                logger.info("PRE-WARMING COMPLETE: GPU and Graph are ready.")
            except Exception as e:
                logger.exception("PRE-WARMING FAILED")

    logger.info("FastAPI Application startup complete")
    yield
    logger.info("Application shutdown")
    await runtime_manager.stop_all()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"{exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "detail": exc.detail
        },
    )
    
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")

    return JSONResponse(
        status_code=500,
        content={
            "status_code": 500,
            "detail": "Unexpected server error"
        },
    )  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    status_code = response.status_code
    logger.info(f"{request.method} {request.url.path} - {status_code} - {duration:.2f}s")
    
    return response

app.include_router(logs)
app.include_router(chat)
app.include_router(auth)
app.include_router(client)
app.include_router(user)
app.include_router(feedback)
app.include_router(agent)
app.include_router(model)
app.include_router(config)