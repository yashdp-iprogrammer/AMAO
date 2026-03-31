from datetime import datetime, timezone
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from src.schema.model_schema import ModelUpdate
from src.Database.models import Model


class ModelRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_model(self, model: Model):
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model


    async def update_model(self, existing_model: Model, model:ModelUpdate):

        update_data = model.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(existing_model, key, value)

        existing_model.updated_at = datetime.now(timezone.utc)

        self.session.add(existing_model)
        await self.session.commit()
        await self.session.refresh(existing_model)
        return existing_model


    async def delete_model(self, existing_model: Model):
        existing_model.is_disabled = True
        self.session.add(existing_model)
        await self.session.commit()


    async def get_model_by_id(self, model_id: str):
        statement = select(Model).where(Model.model_id == model_id, Model.is_disabled == False)
        result = await self.session.exec(statement)
        return result.one_or_none()
    
    async def get_model_by_name(self, model_name: str):
        statement = select(Model).where(Model.model_name == model_name, Model.is_disabled == False)
        result = await self.session.exec(statement)
        return result.one_or_none()


    async def get_all_models(self, page: int, size: int):

        statement = select(Model).where(Model.is_disabled == False)

        count_stmt = select(func.count()).select_from(statement.subquery())
        total_result = (await self.session.exec(count_stmt))
        total = total_result.one()

        offset = (page - 1) * size
        
        statement = statement.offset(offset).limit(size)

        result = await self.session.exec(statement)
        models = result.all()
        
        total_pages = (total + size - 1) // size
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "data": models
        }