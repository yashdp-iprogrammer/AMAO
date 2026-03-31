# from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
# from sqlmodel.ext.asyncio.session import AsyncSession
# from motor.motor_asyncio import AsyncIOMotorClient
# from fastapi import HTTPException

# from src.Database import Database


# class ConnectionFactory:

#     SQL_VENDORS = {"mysql", "postgres", "postgresql", "sqlite", "mssql", "mariadb"}
#     NOSQL_VENDORS = {"mongodb"}

#     DRIVER_MAP = {
#         "mysql": "mysql+aiomysql",
#         "postgres": "postgresql+asyncpg",
#         "postgresql": "postgresql+asyncpg",
#         "sqlite": "sqlite+aiosqlite",
#         "mssql": "mssql+aioodbc",
#         "mariadb": "mariadb+aiomysql"
#     }

#     @classmethod
#     def _build_sql_url(cls, db: dict):

#         db_type = db["db_type"].lower()
#         driver = cls.DRIVER_MAP.get(db_type)

#         if not driver:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Unsupported SQL DB type: {db_type}"
#             )

#         if db_type == "sqlite":
#             return f"{driver}:///{db.get('db_name')}"

#         return (
#             f"{driver}://{db.get('username')}:{db.get('password')}"
#             f"@{db.get('host')}:{db.get('port')}/{db.get('db_name')}"
#         )

#     @classmethod
#     def _build_mongo_uri(cls, db: dict):

#         username = db.get("username")
#         password = db.get("password")

#         if username and password:
#             return (
#                 f"mongodb://{username}:{password}"
#                 f"@{db.get('host')}:{db.get('port')}"
#             )

#         return f"mongodb://{db.get('host')}:{db.get('port')}"

#     @classmethod
#     def create_sql_connection(cls, db_config: dict):

#         database_url = cls._build_sql_url(db_config)


#         db.engine = create_async_engine(
#             database_url,
#             echo=False,
#             pool_size=10,
#             max_overflow=20,
#             pool_pre_ping=True,
#             pool_recycle=3600
#         )

#         db.async_session = async_sessionmaker(
#             bind=db.engine,
#             class_=AsyncSession,
#             expire_on_commit=False
#         )

#         return db

#     @classmethod
#     def create_mongo_connection(cls, db_config: dict):

#         uri = cls._build_mongo_uri(db_config)

#         client = AsyncIOMotorClient(uri)

#         return client[db_config["db_name"]]



from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException

from src.Database.base_db import Database


class ConnectionFactory:

    _registry = {}

    # ----------------------------
    # Registration system
    # ----------------------------

    @classmethod
    def register(cls, db_type: str):
        def decorator(func):
            cls._registry[db_type] = func
            return func
        return decorator

    @classmethod
    def create_connection(cls, db_config: dict):

        db_type = db_config.get("db_type", "").lower()

        creator = cls._registry.get(db_type)

        if not creator:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported database type: {db_type}"
            )

        return creator(db_config)

    # ----------------------------
    # SQL URL builder
    # ----------------------------

    DRIVER_MAP = {
        "mysql": "mysql+aiomysql",
        "postgres": "postgresql+asyncpg",
        "postgresql": "postgresql+asyncpg",
        "sqlite": "sqlite+aiosqlite",
        "mssql": "mssql+aioodbc",
        "mariadb": "mariadb+aiomysql"
    }

    @classmethod
    def _build_sql_uri(cls, db):

        db_type = db["db_type"].lower()
        driver = cls.DRIVER_MAP.get(db_type)

        if not driver:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported SQL DB type: {db_type}"
            )

        if db_type == "sqlite":
            return f"{driver}:///{db.get('db_name')}"

        return (
            f"{driver}://{db.get('username')}:{db.get('password')}"
            f"@{db.get('host')}:{db.get('port')}/{db.get('db_name')}"
        )


# =====================================================
# SQL DATABASES
# =====================================================

@ConnectionFactory.register("mysql")
@ConnectionFactory.register("postgres")
@ConnectionFactory.register("postgresql")
@ConnectionFactory.register("sqlite")
@ConnectionFactory.register("mssql")
@ConnectionFactory.register("mariadb")
def create_sql_connection(db_config: dict):

    uri = ConnectionFactory._build_sql_uri(db_config)

    db = Database(uri)

    db.engine = create_async_engine(
        uri,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600
    )

    db.async_session = async_sessionmaker(
        bind=db.engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    return db


# =====================================================
# MONGODB
# =====================================================

@ConnectionFactory.register("mongodb")
def create_mongodb_connection(db_config: dict):

    username = db_config.get("username")
    password = db_config.get("password")

    if username and password:
        uri = (
            f"mongodb://{username}:{password}"
            f"@{db_config.get('host')}:{db_config.get('port')}"
        )
    else:
        uri = f"mongodb://{db_config.get('host')}:{db_config.get('port')}"

    client = AsyncIOMotorClient(uri)

    return client[db_config["db_name"]]
