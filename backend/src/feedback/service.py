"""Apply completed quiz scores to mastery and create a fresh schedule version."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from src.db.models import FeedbackSuggestion, QuizResult, ScheduleMilestone, SyllabusTopic, TopicLevel
from src.quiz.analysis import DEFAULT_WEAK_THRESHOLD
from src.scheduling.persistence import get_schedule_version
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


def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(value)) if isinstance(value, str) else value


def _create_suggestion(
    db: Session,
    user_id: uuid.UUID,
    topic: SyllabusTopic,
    trigger: str,
) -> FeedbackSuggestion:
    """Return one active check-in suggestion per user/topic/trigger."""
    existing = (
        db.query(FeedbackSuggestion)
        .filter(
            FeedbackSuggestion.user_id == user_id,
            FeedbackSuggestion.topic_id == topic.id,
            FeedbackSuggestion.trigger == trigger,
            FeedbackSuggestion.action == "quiz",
            FeedbackSuggestion.active.is_(True),
        )
        .first()
    )
    if existing is not None:
        return existing

    suggestion = FeedbackSuggestion(
        user_id=user_id,
        topic_id=topic.id,
        trigger=trigger,
        action="quiz",
        message=f"Check in on {topic.name}: take a follow-up quiz to reinforce it.",
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


def get_active_suggestions(
    db: Session, user_id: uuid.UUID | str
) -> list[FeedbackSuggestion]:
    """Return active proactive prompts, newest first, for their owner only."""
    return (
        db.query(FeedbackSuggestion)
        .filter(
            FeedbackSuggestion.user_id == _as_uuid(user_id),
            FeedbackSuggestion.active.is_(True),
        )
        .order_by(FeedbackSuggestion.created_at.desc(), FeedbackSuggestion.id.desc())
        .all()
    )


def dismiss_suggestion(
    db: Session, user_id: uuid.UUID | str, suggestion_id: uuid.UUID | str
) -> bool:
    """Dismiss one owned suggestion so a future event may produce a new one."""
    suggestion = (
        db.query(FeedbackSuggestion)
        .filter(
            FeedbackSuggestion.id == _as_uuid(suggestion_id),
            FeedbackSuggestion.user_id == _as_uuid(user_id),
            FeedbackSuggestion.active.is_(True),
        )
        .first()
    )
    if suggestion is None:
        return False
    suggestion.active = False
    suggestion.dismissed_at = datetime.utcnow()
    db.commit()
    return True


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

        topic_by_id = {topic.id: topic for topic in topics}
        for topic_id, score in averaged_scores.items():
            if score < DEFAULT_WEAK_THRESHOLD:
                _create_suggestion(db, owner_id, topic_by_id[topic_id], "quiz")

    applied_at = datetime.utcnow()
    for result, _ in rows:
        result.feedback_applied_at = applied_at
    db.commit()

    return FeedbackResult(
        quiz_id=attempt_id,
        updated_topic_count=updated_topic_count,
        schedule_version_ids=schedule_version_ids,
    )


def complete_schedule_day(
    db: Session,
    user_id: uuid.UUID | str,
    schedule_id: uuid.UUID | str,
    day_index: int,
) -> ScheduleMilestone:
    """Persist a schedule-day milestone and proactively suggest a quiz check-in.

    A milestone is deliberately explicit: the learner marks a day in a saved
    schedule version complete.  Repeating the same completion is idempotent.
    """
    owner_id = _as_uuid(user_id)
    version = get_schedule_version(db, owner_id, schedule_id)
    if version is None:
        raise ValueError("Schedule not found.")
    if day_index < 0 or day_index >= len(version.plan.days):
        raise ValueError("Schedule day not found.")

    schedule_uuid = _as_uuid(schedule_id)
    milestone = (
        db.query(ScheduleMilestone)
        .filter(
            ScheduleMilestone.user_id == owner_id,
            ScheduleMilestone.schedule_id == schedule_uuid,
            ScheduleMilestone.day_index == day_index,
        )
        .first()
    )
    if milestone is not None:
        return milestone

    milestone = ScheduleMilestone(
        user_id=owner_id, schedule_id=schedule_uuid, day_index=day_index
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)

    for item in version.plan.days[day_index].topics:
        try:
            topic_id = uuid.UUID(item.id)
        except ValueError:
            continue
        topic = (
            db.query(SyllabusTopic)
            .filter(SyllabusTopic.id == topic_id, SyllabusTopic.user_id == owner_id)
            .first()
        )
        if topic is not None:
            # Day-completion suggestions are reinforcement check-ins for newly completed
            # study items, unlike quiz-completion suggestions which are remediation check-ins
            # filtered by weak mastery (< 0.6).
            _create_suggestion(db, owner_id, topic, "schedule_milestone")
    return milestone


