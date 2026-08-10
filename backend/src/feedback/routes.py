"""Query and dismiss proactive feedback suggestions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.db.session import get_db
from src.feedback.schemas import FeedbackSuggestionResponse
from src.feedback.service import dismiss_suggestion, get_active_suggestions

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/suggestions", response_model=list[FeedbackSuggestionResponse])
def list_suggestions(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[FeedbackSuggestionResponse]:
    return get_active_suggestions(db, user_id)


@router.post("/suggestions/{suggestion_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_feedback_suggestion(
    suggestion_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    if not dismiss_suggestion(db, user_id, suggestion_id):
        raise HTTPException(status_code=404, detail="Suggestion not found.")
