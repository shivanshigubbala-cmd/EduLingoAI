import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class TopicPlanItem(BaseModel):
    """A single study topic with a mastery score and optional time estimate."""

    id: str
    title: str
    mastery: float = Field(ge=0.0, le=1.0)
    estimated_hours: int = Field(default=1, ge=1)


class ScheduleRequest(BaseModel):
    """Input for building a study plan from mastery scores."""

    topics: list[TopicPlanItem]
    hours_per_day: int = Field(default=2, ge=1)
    exam_date: date | None = None


class ScheduleDay(BaseModel):
    """A single day in the generated study plan."""

    label: str
    topics: list[TopicPlanItem]


class SchedulePlan(BaseModel):
    """Daily study plan ordered by weak topics first."""

    days: list[ScheduleDay]


class ScheduleVersion(BaseModel):
    """An immutable, persisted schedule version."""

    version_id: uuid.UUID
    created_at: datetime
    plan: SchedulePlan
class ScheduleExplanation(BaseModel):
    """A chat-style message explaining the reasoning behind a schedule."""

    message: str