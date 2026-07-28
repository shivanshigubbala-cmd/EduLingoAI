"""Diagnostic module — P3-SHI6 knowledge-level scoring."""

from src.diagnostic.schemas import DiagnosticAnswer
from src.diagnostic.scoring import apply_mastery_scores, score_diagnostic

__all__ = [
    "DiagnosticAnswer",
    "score_diagnostic",
    "apply_mastery_scores",
]
