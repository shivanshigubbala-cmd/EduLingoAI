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


class TopicScoreBreakdown(BaseModel):
    """One topic's score within a specific quiz attempt."""

    topic_id: uuid.UUID
    topic_name: str
    questions_total: int
    questions_answered: int
    average_score: float | None
    is_weak: bool


class QuizScoreAnalysis(BaseModel):
    """Results-screen analysis derived from the persisted quiz rows."""

    quiz_id: uuid.UUID
    total_questions: int
    graded_questions: int
    average_score: float | None
    weak_threshold: float
    topics: list[TopicScoreBreakdown]
