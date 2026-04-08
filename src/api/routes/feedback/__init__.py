from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from src.schema.user_schema import CurrentUser
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.feedback_service import FeedbackService
from src.schema.feedback_schema import FeedbackCreate,FeedbackRead,FeedbackUpdate,FeedbackResponse,FeedbackResponseList
from src.Database import system_db as db
from src.security.o_auth import auth_dependency
from src.utils.logger import logger


router = APIRouter(prefix="/feedbacks", tags=["Feedbacks"])


def get_feedback_service(session: AsyncSession = Depends(db.get_session)) -> FeedbackService:
    return FeedbackService(session)

feedback_session = Annotated[FeedbackService, Depends(get_feedback_service)]


@router.post("/add-feedback", response_model=FeedbackResponse)
async def add_feedback(
    feedback: FeedbackCreate,
    service: feedback_session,
    current_user: CurrentUser = Depends(
        auth_dependency.require_roles(["SuperAdmin", "Admin", "User"])
    )
):
    logger.info(f"[CREATE_FEEDBACK] user={current_user}, payload={feedback.model_dump()}")

    return await service.create_feedback(feedback, current_user)


@router.put("/update-feedback/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback(
    feedback_id: str,
    feedback: FeedbackUpdate,
    service: feedback_session,
    current_user: CurrentUser = Depends(
        auth_dependency.require_roles(["SuperAdmin", "Admin", "User"])
    )
):
    logger.info(f"[UPDATE_FEEDBACK] user={current_user}, feedback_id={feedback_id}")

    return await service.update_feedback(feedback_id, feedback, current_user)


@router.delete("/remove-feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    service: feedback_session,
    current_user: CurrentUser = Depends(
        auth_dependency.require_roles(["SuperAdmin", "Admin", "User"])
    )
):
    logger.info(f"[DELETE_FEEDBACK] user={current_user}, feedback_id={feedback_id}")

    return await service.delete_feedback(feedback_id, current_user)


@router.get("/list-feedbacks", response_model=FeedbackResponseList)
async def list_feedback(
    service: feedback_session,
    client_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    current_user: CurrentUser = Depends(
        auth_dependency.require_roles(["SuperAdmin", "Admin", "User"])
    )
):
    logger.info(f"[LIST_FEEDBACK] user={current_user}, client_id={client_id}, page={page}, size={size}")

    return await service.get_all_feedback(current_user, client_id, page, size)


@router.get("/get-feedback/{feedback_id}", response_model=FeedbackRead)
async def get_feedback_by_id(
    feedback_id: str,
    service: feedback_session,
    current_user: CurrentUser = Depends(
        auth_dependency.require_roles(["SuperAdmin", "Admin", "User"])
    )
):
    logger.info(f"[GET_FEEDBACK] user={current_user}, feedback_id={feedback_id}")

    return await service.get_feedback_by_id(feedback_id, current_user)