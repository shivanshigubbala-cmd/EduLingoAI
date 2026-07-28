"""Diagnostic answer schemas — P3-SHI6 stub input boundary."""

import uuid
from pydantic import BaseModel, Field, field_validator


class DiagnosticAnswer(BaseModel):
    """Stub input shape for a single answered diagnostic question.

    Mirrors the structure of quiz_results (docs/schema.md) so it can be seamlessly
    swapped when P3-SRE6 (diagnostic question generator) lands.
    """

    topic_id: uuid.UUID
    question: str
    is_correct: bool
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("topic_id", mode="before")
    @classmethod
    def parse_uuid(cls, v: uuid.UUID | str) -> uuid.UUID:
        if isinstance(v, str):
            return uuid.UUID(v)
        return v
