from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.model_repository import ModelRepo
from src.Database.models import Model
from src.schema.model_schema import ModelCreate, ModelUpdate
from src.schema.user_schema import CurrentUser
from uuid import uuid4
from src.utils.logger import logger


class ModelService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model_repo = ModelRepo(session)

    async def create_model(self, model: ModelCreate):
        logger.info(f"[MODEL] Creating model: {model.model_name}")

        existing_model = await self.model_repo.get_model_by_name(model.model_name)
        if existing_model:
            logger.warning(f"[MODEL] Model already exists: {model.model_name}")
            raise HTTPException(status_code=400, detail="Model already exists")

        model = Model(
            model_id=str(uuid4()),
            model_name=model.model_name,
            token_size=model.token_size,
            model_subscription=model.model_subscription,
            subscription_cost=model.subscription_cost,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        created_model = await self.model_repo.create_model(model)

        logger.info(f"[MODEL] Model created successfully: {model.model_id}")

        return {
            "message": "Model created successfully",
            "model": created_model
        }

    async def update_model(self, model_id: str, model: ModelUpdate):
        logger.info(f"[MODEL] Updating model: {model_id}")

        existing_model = await self.model_repo.get_model_by_id(model_id)
        if not existing_model:
            logger.warning(f"Model not found for update: {model_id}")
            raise HTTPException(status_code=404, detail="Model not found")

        updated_model = await self.model_repo.update_model(existing_model, model)

        logger.info(f"[MODEL] Model updated successfully: {model_id}")

        return {
            "message": "Model updated successfully",
            "model": updated_model
        }

    async def delete_model(self, model_id: str):
        logger.info(f"[MODEL] Deleting model: {model_id}")

        existing_model = await self.model_repo.get_model_by_id(model_id)
        if not existing_model:
            logger.warning(f"[MODEL] Model not found for deletion: {model_id}")
            raise HTTPException(status_code=404, detail="Model not found")

        await self.model_repo.delete_model(existing_model)

        logger.info(f"[MODEL] Model deleted successfully: {model_id}")

        return {"message": "Model deleted successfully"}


    async def get_all_models(self, page: int, size: int, current_user: CurrentUser):
        logger.info(f"[MODEL] Fetching all models | page={page}, size={size}")
        return await self.model_repo.get_all_models(page, size)


    async def get_model_by_id(self, model_id: str, current_user: CurrentUser):
        logger.info(f"[MODEL] Fetching model by id: {model_id}")

        model = await self.model_repo.get_model_by_id(model_id)

        if not model:
            logger.warning(f"[MODEL] Model not found: {model_id}")
            raise HTTPException(status_code=404, detail="Model not found")

        return model