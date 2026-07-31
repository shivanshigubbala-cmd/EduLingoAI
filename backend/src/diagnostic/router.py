"""Diagnostic session routes — P3-SRE7 adaptive answer submission."""
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.db.session import get_db
from src.db.models import ChatMessage, Session as SessionModel
from src.diagnostic.adaptive import record_answer, select_next_question
from src.diagnostic.schemas import AnswerSubmission, AnswerResult, DiagnosticQuestionPublic

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


@router.post("/sessions/{session_id}/answers", response_model=AnswerResult)
def submit_answer(
    session_id: uuid.UUID,
    submission: AnswerSubmission,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Grade an answer, record it, and return the adaptively-selected next question.

    Adaptivity rule (P3-SRE7): correct -> next question from a different
    unit; incorrect -> next question from the same unit if one remains.
    """
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Diagnostic session not found.")

    try:
        is_correct = record_answer(db, session_id, submission.question_id, submission.answer_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    answered_question = (
        db.query(ChatMessage).filter(ChatMessage.id == submission.question_id).first()
    )
    last_topic_id = answered_question.topic_reference_id if answered_question else None

    next_q = select_next_question(
        db, session_id, last_was_correct=is_correct, last_topic_id=last_topic_id
    )

    if next_q is None:
        session.ended_at = datetime.utcnow()
        db.commit()
        return AnswerResult(is_correct=is_correct, next_question=None, session_complete=True)

    next_data = json.loads(next_q.content)
    next_public = DiagnosticQuestionPublic(
        id=next_q.id,
        topic_id=next_q.topic_reference_id,
        topic_name=next_data["topic_name"],
        question_type=next_data["question_type"],
        question_text=next_data["question_text"],
        options=next_data.get("options"),
    )

    return AnswerResult(is_correct=is_correct, next_question=next_public, session_complete=False)