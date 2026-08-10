"""Apply completed quiz scores to mastery and create a fresh schedule version."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from src.db.models import QuizResult, SyllabusTopic, TopicLevel
from src.diagnostic.scoring import apply_mastery_scores
from src.scheduling.persistence import persist_schedule
from src.scheduling.schemas import ScheduleRequest, TopicPlanItem
from src.scheduling.service import build_schedule


DEFAULT_MASTERY_FOR_UNSCORED = 0.5


@dataclass(frozen=True)
class FeedbackResult:
    """The durable effects created when a completed quiz feeds back."""

    quiz_id: uuid.UUID
    updated_topic_count: int
    schedule_version_ids: list[uuid.UUID]


def apply_quiz_feedback(
    db: Session,
    user_id: uuid.UUID | str,
    quiz_id: uuid.UUID | str,
) -> FeedbackResult | None:
    """Update mastery and schedules once all questions in a quiz are graded.

    Returns ``None`` until every persisted question has a score, or after the
    quiz has already been applied.  Raw ``QuizResult`` rows are never changed
    beyond their idempotency marker.
    """
    owner_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    attempt_id = uuid.UUID(str(quiz_id)) if isinstance(quiz_id, str) else quiz_id
    rows = (
        db.query(QuizResult, SyllabusTopic.document_id)
        .join(SyllabusTopic, QuizResult.topic_id == SyllabusTopic.id)
        .filter(QuizResult.user_id == owner_id, QuizResult.quiz_id == attempt_id)
        .all()
    )
    if not rows:
        raise ValueError("Quiz not found.")
    if any(result.score is None for result, _ in rows):
        return None
    if any(result.feedback_applied_at is not None for result, _ in rows):
        return None

    scores_by_document: dict[uuid.UUID, dict[uuid.UUID, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for result, document_id in rows:
        scores_by_document[document_id][result.topic_id].append(float(result.score))

    updated_topic_count = 0
    schedule_version_ids: list[uuid.UUID] = []
    for document_id, topic_scores in scores_by_document.items():
        averaged_scores = {
            topic_id: sum(scores) / len(scores) for topic_id, scores in topic_scores.items()
        }
        # Overwrites mastery with this quiz's result, consistent with P3-SHI6's
        # diagnostic convention — no blending with prior assessments; a
        # completed quiz is the newest authoritative signal for its topics.
        updated_topic_count += apply_mastery_scores(
            db, owner_id, document_id, averaged_scores
        )

        topics = (
            db.query(SyllabusTopic)
            .filter(
                SyllabusTopic.user_id == owner_id,
                SyllabusTopic.document_id == document_id,
                SyllabusTopic.level == TopicLevel.topic,
            )
            .all()
        )
        plan = build_schedule(
            ScheduleRequest(
                topics=[
                    TopicPlanItem(
                        id=str(topic.id),
                        title=topic.name,
                        mastery=(
                            topic.mastery
                            if topic.mastery is not None
                            else DEFAULT_MASTERY_FOR_UNSCORED
                        ),
                    )
                    for topic in topics
                ]
            )
        )
        schedule_version_ids.append(persist_schedule(db, owner_id, plan).version_id)

    applied_at = datetime.utcnow()
    for result, _ in rows:
        result.feedback_applied_at = applied_at
    db.commit()

    return FeedbackResult(
        quiz_id=attempt_id,
        updated_topic_count=updated_topic_count,
        schedule_version_ids=schedule_version_ids,
    )
