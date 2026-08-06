"""Quiz answer-submission schemas — P6-SHR9."""

import uuid

from pydantic import BaseModel


class QuizAnswerSubmission(BaseModel):
    answer_text: str


class QuizAnswerResult(BaseModel):
    """Grading result for a single quiz question.

    is_correct is None for short-answer questions where grading yields a
    partial score rather than a strict binary — score is the authoritative
    signal in that case.
    """

    quiz_result_id: uuid.UUID
    is_correct: bool | None
    score: float
    rationale: str