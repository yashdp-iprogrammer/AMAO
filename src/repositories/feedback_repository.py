from datetime import datetime, timezone
from fastapi import HTTPException
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from src.Database.models import Feedback, Log
from src.schema.user_schema import CurrentUser
from src.schema.feedback_schema import FeedbackUpdate


class FeedbackRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_feedback(self, feedback: Feedback, current_user: CurrentUser, log: Log):

        if current_user.role_name == "SuperAdmin":
            pass
        elif current_user.role_name == "Admin":
            if log.client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="Admin can only add feedback to logs within their own client")
        elif current_user.role_name == "User":
            if log.user_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="You are not allowed to create feedback for this log")

        self.session.add(feedback)
        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback

    async def update_feedback(self, existing_feedback: Feedback, feedback: FeedbackUpdate, current_user: CurrentUser):

        log_stmt = select(Log).where(Log.log_id == existing_feedback.log_id)
        log_result = (await self.session.exec(log_stmt))
        log = log_result.one_or_none()

        if current_user.role_name == "Admin":
            if log.client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="Admin can only update feedback for logs within their own client")

        if current_user.role_name == "User" :
            if log.user_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="You are not allowed to update this feedback")
            
        update_data = feedback.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(existing_feedback, key, value)

        existing_feedback.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(existing_feedback)
        return existing_feedback


    async def delete_feedback(self, feedback: Feedback, current_user: CurrentUser):

        log_stmt = select(Log).where(Log.log_id == feedback.log_id)
        log = (await self.session.exec(log_stmt)).one_or_none()

        if current_user.role_name == "Admin":
            if log.client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="Admin can only delete feedback for logs within their own client")

        if current_user.role_name == "User":
            if log.user_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="You are not allowed to delete this feedback")
        feedback.is_disabled = True
        feedback.updated_at = datetime.now(timezone.utc)

        self.session.add(feedback)
        await self.session.commit()


    async def get_all_feedback(self, current_user: CurrentUser, client_id: int, page:int, size:int):

        statement = select(Feedback).join(Log).where(Feedback.is_disabled == False)

        if current_user.role_name == "SuperAdmin":
            if client_id:
                statement = statement.where(Log.client_id == client_id)

        elif current_user.role_name == "Admin":
            if client_id and client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="Admin can only access feedback for their own client")
            statement = statement.where(Log.client_id == current_user.client_id)

        elif current_user.role_name == "User":
            if client_id and client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="You are not allowed to access feedback for this client")
            statement = statement.where(Log.user_id == current_user.user_id)

        else:
            raise HTTPException(status_code=403, detail="You are not allowed to access feedback details")

        count_stmt = select(func.count()).select_from(statement.subquery())
        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        offset = (page - 1) * size
        statement = statement.offset(offset).limit(size)

        result = await self.session.exec(statement)
        feedbacks = result.all()

        total_pages = (total + size - 1) // size

        return {
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "data": feedbacks
        }


    async def get_feedback_by_id(self, feedback_id: int, current_user: CurrentUser):
        if current_user.role_name == "SuperAdmin":
            pass
        elif current_user.role_name == "Admin":
            stmt = select(Feedback).join(Log).where(Feedback.feedback_id == feedback_id, Feedback.is_disabled == False, Log.client_id == current_user.client_id)
            result = await self.session.exec(stmt)
            feedback = result.one_or_none()
            return feedback
        stmt = select(Feedback).where(Feedback.feedback_id == feedback_id, Feedback.is_disabled == False)
        result = await self.session.exec(stmt)
        feedback = result.one_or_none()
        return feedback