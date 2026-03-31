from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.model_repository import ModelRepo
from src.Database.models import Model
from src.schema.model_schema import ModelCreate, ModelUpdate
from src.schema.user_schema import CurrentUser
from uuid import uuid4


class ModelService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model_repo = ModelRepo(session)

    async def create_model(self, model: ModelCreate):

        existing_model = await self.model_repo.get_model_by_name(model.model_name)
        if existing_model:
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

        return {
            "message": "Model created successfully",
            "model": created_model
        }

    async def update_model(self, model_id: str, model: ModelUpdate):

        existing_model = await self.model_repo.get_model_by_id(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")

        updated_model = await self.model_repo.update_model(existing_model, model)

        return {
            "message": "Model updated successfully",
            "model": updated_model
        }

    async def delete_model(self, model_id: str):

        existing_model = await self.model_repo.get_model_by_id(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")

        await self.model_repo.delete_model(existing_model)
        return {"message": "Model deleted successfully"}


    async def get_all_models(self, page: int, size: int, current_user: CurrentUser):
        return await self.model_repo.get_all_models(page, size)


    async def get_model_by_id(self, model_id: str, current_user: CurrentUser):
        model = await self.model_repo.get_model_by_id(model_id)

        if not model:
            raise HTTPException(status_code=404, detail="Model not found")

        return model