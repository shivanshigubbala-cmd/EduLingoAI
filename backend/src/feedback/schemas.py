"""Public schemas for proactive feedback suggestions."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class FeedbackSuggestionResponse(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    trigger: str
    action: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
