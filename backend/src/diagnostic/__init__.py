"""Diagnostic package — P3-SHI6 scoring + P3-SRE6/P3-SRE7 generation/adaptive flow."""

from src.diagnostic.adaptive import grade_answer, record_answer, select_next_question
from src.diagnostic.generator import generate_diagnostic_questions
from src.diagnostic.persistence import create_diagnostic_session
from src.diagnostic.schemas import (
    AnswerResult,
    AnswerSubmission,
    DiagnosticAnswer,
    DiagnosticQuestionPublic,
    DiagnosticSessionResponse,
    QuestionType,
)
from src.diagnostic.scoring import apply_mastery_scores, score_diagnostic

__all__ = [
    "generate_diagnostic_questions",
    "create_diagnostic_session",
    "grade_answer",
    "record_answer",
    "select_next_question",
    "DiagnosticAnswer",
    "DiagnosticQuestionPublic",
    "DiagnosticSessionResponse",
    "AnswerSubmission",
    "AnswerResult",
    "QuestionType",
    "score_diagnostic",
    "apply_mastery_scores",
]
