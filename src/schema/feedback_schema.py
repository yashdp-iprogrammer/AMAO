from typing import Optional, List
from pydantic import BaseModel

class FeedbackCreate(BaseModel):
    log_id: str
    feedback: bool


class FeedbackUpdate(BaseModel):
    feedback: Optional[bool] = None


class FeedbackRead(BaseModel):
    feedback_id: str
    log_id: str
    feedback: bool


class FeedbackResponse(BaseModel):
    message: str
    feedback: FeedbackRead


class FeedbackResponseList(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    data: List[FeedbackRead]
