from uuid import uuid4
from fastapi import HTTPException
from datetime import datetime, timezone
from src.Database.models import Feedback
from src.schema.user_schema import CurrentUser
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.log_repository import LogRepo
from src.repositories.feedback_repository import FeedbackRepo
from src.schema.feedback_schema import FeedbackCreate, FeedbackUpdate


class FeedbackService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.feedback_repo = FeedbackRepo(session)
        self.log_repo = LogRepo(session)

    async def create_feedback(self, feedback: FeedbackCreate, current_user: CurrentUser):
        existing_log = await self.log_repo.get_log_by_id(feedback.log_id)
        if not existing_log:
            raise HTTPException(status_code=404, detail="Log not found")

        feedback = Feedback(
            feedback_id=str(uuid4()),
            log_id=feedback.log_id,
            feedback=feedback.feedback,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        created_feedback = await self.feedback_repo.create_feedback(feedback, current_user, existing_log)

        return {
            "message": "Feedback created successfully",
            "feedback": created_feedback
        }


    async def update_feedback(self, feedback_id: int, feedback: FeedbackUpdate, current_user: CurrentUser):
        existing_feedback = await self.feedback_repo.get_feedback_by_id(feedback_id, current_user)

        if not existing_feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        updated_feedback = await self.feedback_repo.update_feedback(existing_feedback, feedback, current_user)
        return {
            "message": "Feedback updated successfully",
            "feedback": updated_feedback
        }
    
    
    async def delete_feedback(self, feedback_id: str, current_user: CurrentUser):
        existing_feedback = await self.feedback_repo.get_feedback_by_id(feedback_id, current_user)

        if not existing_feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        await self.feedback_repo.delete_feedback(existing_feedback, current_user)

        return {"message": "Feedback deleted successfully"}
    

    async def get_all_feedback(self, current_user: CurrentUser, client_id: int, page: int = 1, size: int = 10):
        return await self.feedback_repo.get_all_feedback(current_user, client_id, page, size)


    async def get_feedback_by_id(self, feedback_id: str, current_user: CurrentUser):
        feedback = await self.feedback_repo.get_feedback_by_id(feedback_id, current_user)

        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        return feedback
