"""Pydantic schemas for diagnostic question generation and scoring."""

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


class DiagnosticAnswer(BaseModel):
    """Diagnostic evaluation result mapped from P3-SRE6 output.

    Note: P3-SRE6 does NOT provide a calibrated difficulty value,
    so this field is hardcoded to a neutral default (0.5) in the adapter.
    Once DiagnosticQuestion exposes a real difficulty value, replace the
    adapter default — no other change needed.
    """

    is_correct: bool
    topic_id: uuid.UUID | None
    question: str | None
    session_complete: bool = False
    difficulty: float = 0.5


def adapt_answer_result(result: AnswerResult) -> DiagnosticAnswer:
    """Convert Sreehitha's AnswerResult into DiagnosticAnswer.

    Because her return type (AnswerResult with a nested DiagnosticQuestionPublic)
    differs from the original flat stub, this adapter extracts the fields needed
    by scoring/evaluation consumers without changing score_diagnostic internals.
    """
    next_q = result.next_question
    return DiagnosticAnswer(
        is_correct=result.is_correct,
        topic_id=result.answered_topic_id,
        question=next_q.question_text if next_q else None,
        session_complete=result.session_complete,
        difficulty=0.5,
    )
