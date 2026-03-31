import time
from fastapi import FastAPI
from src.Database import system_db as db
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.utils.db_seeder import seed_initial_data


from src.api.routes.auth import router as auth
from src.api.routes.chat import router as chat
from src.api.routes.clients import router as client
from src.api.routes.user import router as user
from src.api.routes.feedback import router as feedback
from src.api.routes.agents import router as agent
from src.api.routes.models import router as model
from src.api.routes.logs import router as logs
from src.api.routes.configs import router as config


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db(db.engine)
    async with db.async_session() as session:
        await seed_initial_data(session)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    print(f"{request.url.path} took {duration:.2f}s")
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
