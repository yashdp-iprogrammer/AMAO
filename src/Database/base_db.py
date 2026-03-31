
from fastapi.concurrency import asynccontextmanager
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine
from src.settings.config import config
from src.utils.logger import logger

class Database:
    def __init__(self, db_url: str):
        logger.info(f"Creating async database engine with URL: {db_url}")
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)
        logger.info("Async database engine created successfully")

    async def init_db(self, engine: AsyncEngine):
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def get_session(self):
        logger.debug("Opening new async database session")
        async with self.async_session() as session:
            try:
                yield session
            finally:
                logger.debug("Closing async database session")
                
    @asynccontextmanager
    async def session_scope(self):
        async with self.async_session() as session:
            yield session
            
            
    def get_schema_text(self) -> str:
        schema_lines = []

        for table in SQLModel.metadata.sorted_tables:
            schema_lines.append(f"Table: {table.name}")

            for column in table.columns:
                col_line = f"  - {column.name} ({column.type})"

                if column.primary_key:
                    col_line += " PRIMARY KEY"

                if column.foreign_keys:
                    for fk in column.foreign_keys:
                        col_line += f" FOREIGN KEY → {fk.target_fullname}"

                schema_lines.append(col_line)

            schema_lines.append("")  # spacing between tables

        return "\n".join(schema_lines)
