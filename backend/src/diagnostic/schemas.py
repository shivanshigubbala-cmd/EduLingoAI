"""Pydantic schemas for diagnostic question generation — P3-SRE6."""
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    mcq = "mcq"
    short_answer = "short_answer"


class DiagnosticQuestion(BaseModel):
    """Full question, including the correct answer — never sent to the client."""

    topic_name: str
    question_type: QuestionType
    question_text: str
    options: list[str] | None = Field(
        default=None,
        description="Present only for mcq; null for short_answer.",
    )
    correct_answer: str


class DiagnosticQuestionSet(BaseModel):
    """LLM output shape: a flat list of generated questions."""

    questions: list[DiagnosticQuestion] = Field(default_factory=list)


class DiagnosticQuestionPublic(BaseModel):
    """Client-facing question — correct_answer is intentionally omitted."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    topic_id: uuid.UUID | None
    topic_name: str
    question_type: QuestionType
    question_text: str
    options: list[str] | None = None


class DiagnosticSessionResponse(BaseModel):
    session_id: uuid.UUID
    questions: list[DiagnosticQuestionPublic]

class AnswerSubmission(BaseModel):
    question_id: uuid.UUID
    answer_text: str


class AnswerResult(BaseModel):
    is_correct: bool
    next_question: DiagnosticQuestionPublic | None
    session_complete: bool
    answered_topic_id: uuid.UUID | None = None