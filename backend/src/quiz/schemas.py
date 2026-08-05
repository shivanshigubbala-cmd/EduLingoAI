"""Pydantic schemas for quiz generation — P6-SHR8."""

import uuid
from enum import Enum

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    mcq = "mcq"
    short_answer = "short_answer"


class QuizQuestion(BaseModel):
    """Full question, including the correct answer — never sent to the client."""

    topic_name: str
    question_type: QuestionType
    question_text: str
    options: list[str] | None = Field(
        default=None,
        description="Present only for mcq; null for short_answer.",
    )
    correct_answer: str


class QuizQuestionSet(BaseModel):
    """LLM output shape: a flat list of generated quiz questions."""

    questions: list[QuizQuestion] = Field(default_factory=list)


class QuizQuestionPublic(BaseModel):
    """Client-facing question — correct_answer intentionally omitted."""

    model_config = {"from_attributes": True}

    id: uuid.UUID | None = None
    topic_id: uuid.UUID
    topic_name: str
    question_type: QuestionType
    question_text: str
    options: list[str] | None = None


class QuizResponse(BaseModel):
    """Response shape for a generated quiz."""

    quiz_id: uuid.UUID
    questions: list[QuizQuestionPublic]