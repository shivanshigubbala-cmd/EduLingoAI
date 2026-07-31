"""Diagnostic package — P3-SRE6 (question generation) & P3-SRE7 (adaptive flow)."""
from src.diagnostic.adaptive import grade_answer, record_answer, select_next_question
from src.diagnostic.generator import generate_diagnostic_questions
from src.diagnostic.persistence import create_diagnostic_session
from src.diagnostic.schemas import (
    AnswerResult,
    AnswerSubmission,
    DiagnosticQuestionPublic,
    DiagnosticSessionResponse,
    QuestionType,
)

__all__ = [
    "generate_diagnostic_questions",
    "create_diagnostic_session",
    "grade_answer",
    "record_answer",
    "select_next_question",
    "DiagnosticQuestionPublic",
    "DiagnosticSessionResponse",
    "AnswerSubmission",
    "AnswerResult",
    "QuestionType",
]