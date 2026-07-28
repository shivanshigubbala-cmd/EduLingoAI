"""Pydantic schemas for topic tree extraction — P2-SHI4."""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class Topic(BaseModel):
    name: str
    subtopics: list[str] = Field(default_factory=list)
    mastery: Literal[None] = None

    @field_validator("mastery", mode="before")
    @classmethod
    def force_mastery_none(cls, v: str | int | float | None) -> None:
        """Safety net: force mastery to None post-parse even if LLM hallucinates a number/value."""
        return None


class Unit(BaseModel):
    name: str
    topics: list[Topic] = Field(default_factory=list)


class TopicTreeResponse(BaseModel):
    subject: str
    units: list[Unit] = Field(default_factory=list)
