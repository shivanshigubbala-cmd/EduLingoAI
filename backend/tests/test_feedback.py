"""P7-TEAM3 tests for completed-quiz mastery and schedule feedback."""

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.models import (
    Document,
    DocumentStatus,
    QuizResult,
    SyllabusTopic,
    TopicLevel,
    User,
)
from src.feedback import apply_quiz_feedback
from src.scheduling.persistence import get_schedule_history, persist_schedule
from src.scheduling.schemas import ScheduleRequest, TopicPlanItem
from src.scheduling.service import build_schedule


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_quiz(db):
    user = User(email="feedback@example.com", hashed_password="hashed")
    db.add(user)
    db.flush()
    document = Document(
        user_id=user.id,
        filename="course.pdf",
        storage_path="course.pdf",
        mime_type="application/pdf",
        status=DocumentStatus.parsed,
    )
    db.add(document)
    db.flush()
    now_strong = SyllabusTopic(
        user_id=user.id,
        document_id=document.id,
        name="Now weak",
        level=TopicLevel.topic,
        mastery=0.9,
    )
    now_strong_other = SyllabusTopic(
        user_id=user.id,
        document_id=document.id,
        name="Initially weak",
        level=TopicLevel.topic,
        mastery=0.2,
    )
    db.add_all([now_strong, now_strong_other])
    db.flush()
    quiz_id = uuid.uuid4()
    db.add_all(
        [
            QuizResult(
                user_id=user.id,
                topic_id=now_strong.id,
                quiz_id=quiz_id,
                question="q1",
                score=0.0,
            ),
            QuizResult(
                user_id=user.id,
                topic_id=now_strong_other.id,
                quiz_id=quiz_id,
                question="q2",
                score=1.0,
            ),
        ]
    )
    db.commit()
    return user, document, now_strong, now_strong_other, quiz_id


def test_completed_quiz_updates_mastery_prioritizes_weak_topic_and_keeps_history():
    db = _session()
    user, _document, now_weak, initially_weak, quiz_id = _seed_quiz(db)
    before = build_schedule(
        ScheduleRequest(
            topics=[
                TopicPlanItem(id=str(now_weak.id), title=now_weak.name, mastery=0.9),
                TopicPlanItem(id=str(initially_weak.id), title=initially_weak.name, mastery=0.2),
            ]
        )
    )
    first_version = persist_schedule(db, user.id, before)

    feedback = apply_quiz_feedback(db, user.id, quiz_id)

    assert feedback is not None
    assert feedback.updated_topic_count == 2
    db.refresh(now_weak)
    db.refresh(initially_weak)
    assert now_weak.mastery == 0.0
    assert initially_weak.mastery == 1.0

    history = get_schedule_history(db, user.id)
    assert len(history) == 2
    previous = next(version for version in history if version.version_id == first_version.version_id)
    regenerated = next(
        version for version in history if version.version_id == feedback.schedule_version_ids[0]
    )
    assert previous.plan.days[0].topics[0].id == str(initially_weak.id)
    assert regenerated.plan.days[0].topics[0].id == str(now_weak.id)


def test_feedback_waits_for_completion_and_is_idempotent():
    db = _session()
    user, _document, now_weak, initially_weak, quiz_id = _seed_quiz(db)
    pending = (
        db.query(QuizResult)
        .filter(QuizResult.quiz_id == quiz_id, QuizResult.topic_id == initially_weak.id)
        .one()
    )
    pending.score = None
    db.commit()

    assert apply_quiz_feedback(db, user.id, quiz_id) is None
    db.refresh(now_weak)
    assert now_weak.mastery == 0.9
    assert get_schedule_history(db, user.id) == []

    pending.score = 1.0
    db.commit()
    first = apply_quiz_feedback(db, user.id, quiz_id)
    assert first is not None
    assert apply_quiz_feedback(db, user.id, quiz_id) is None
    assert len(get_schedule_history(db, user.id)) == 1
