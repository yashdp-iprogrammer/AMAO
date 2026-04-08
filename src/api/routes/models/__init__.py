from fastapi import APIRouter, Depends, Query
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from src.schema.model_schema import ModelCreate, ModelUpdate, ModelRead, ModelResponse, ModelResponseList
from src.services.model_service import ModelService
from src.Database import system_db as db
from src.security.o_auth import auth_dependency
from src.utils.logger import logger



router = APIRouter(prefix="/models", tags=["Models"])


def get_model_service(session: AsyncSession = Depends(db.get_session)) -> ModelService:
    return ModelService(session)

model_session = Annotated[ModelService, Depends(get_model_service)]


@router.post("/add-model", response_model=ModelResponse)
async def create_model(
    model: ModelCreate,
    service: model_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[CREATE_MODEL] user_id={current_user.user_id}, model_name={model.model_name}")
    return await service.create_model(model)


@router.put("/update-model/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    model: ModelUpdate,
    service: model_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[UPDATE_MODEL] user_id={current_user.user_id}, model_id={model_id}")
    return await service.update_model(model_id, model)


@router.delete("/remove-model/{model_id}")
async def delete_model(
    model_id: str,
    service: model_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin"]))
):
    logger.info(f"[DELETE_MODEL] user_id={current_user.user_id}, model_id={model_id}")
    return await service.delete_model(model_id)


@router.get("/list-models", response_model=ModelResponseList)
async def get_all_models(
    service: model_session,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin", "User"]))
):
    logger.info(f"[LIST_MODELS] user_id={current_user.user_id}, page={page}, size={size}")
    return await service.get_all_models(page, size, current_user)


@router.get("/get-model/{model_id}", response_model=ModelRead)
async def get_model_by_id(
    model_id: str,
    service: model_session,
    current_user=Depends(auth_dependency.require_roles(["SuperAdmin", "Admin", "User"]))
):
    logger.info(f"[GET_MODEL] user_id={current_user.user_id}, model_id={model_id}")
    return await service.get_model_by_id(model_id, current_user)