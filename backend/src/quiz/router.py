"""Quiz answer submission and grading routes — P6-SHR9.

Persistence model: POST /documents/{id}/quiz (P6-SHR8) writes one
QuizResult row per generated question, storing the full question — INCLUDING
correct_answer and question_type — as JSON in the existing `question`
column. This mirrors how the diagnostic module stores its answer key in
ChatMessage.content (src/diagnostic/persistence.py), so no new migration
was needed for P6-SHR9's grading to work.
"""
import json
import uuid


from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.db.session import get_db
from src.db.models import QuizResult
from src.quiz.grading import grade_answer
from src.quiz.analysis import DEFAULT_WEAK_THRESHOLD, analyze_quiz_results
from src.quiz.answer_schemas import QuizAnswerSubmission, QuizAnswerResult, QuizScoreAnalysis
from src.feedback import apply_quiz_feedback

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.get("/{quiz_id}/analysis", response_model=QuizScoreAnalysis)
def get_quiz_analysis(
    quiz_id: uuid.UUID,
    weak_threshold: float = Query(DEFAULT_WEAK_THRESHOLD, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> QuizScoreAnalysis:
    """Return per-topic scores and weak-area flags for a quiz attempt (P6-SHI11)."""
    try:
        return analyze_quiz_results(db, user_id, quiz_id, weak_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{quiz_result_id}/answer", response_model=QuizAnswerResult)
def submit_quiz_answer(
    quiz_result_id: uuid.UUID,
    submission: QuizAnswerSubmission,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Grade a single quiz answer: MCQ by exact match, short-answer via LLM rubric.

    P6-SHR9. Depends on P6-SHR8 (quiz generation, which persists the answer
    key needed here).
    """
    result_row = (
        db.query(QuizResult)
        .filter(QuizResult.id == quiz_result_id, QuizResult.user_id == user_id)
        .first()
    )
    if result_row is None:
        raise HTTPException(status_code=404, detail="Quiz question not found.")

    try:
        question_data = json.loads(result_row.question)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored question data is corrupted and cannot be graded.",
        ) from exc

    grading = grade_answer(
        question_type=question_data["question_type"],
        question_text=question_data["question_text"],
        correct_answer=question_data["correct_answer"],
        student_answer=submission.answer_text,
    )

    result_row.student_answer = submission.answer_text
    result_row.is_correct = grading["is_correct"]
    result_row.score = grading["score"]
    result_row.rationale = grading["rationale"]
    db.commit()

    # A completed attempt automatically feeds scores back into mastery and
    # persists a new immutable schedule version.  Incomplete attempts are a
    # no-op, so this remains safe to call after every submitted answer.
    apply_quiz_feedback(db, user_id, result_row.quiz_id)

    return QuizAnswerResult(
        quiz_result_id=result_row.id,
        is_correct=grading["is_correct"],
        score=grading["score"],
        rationale=grading["rationale"],
    )
