"""Tests for P6-SHI11 per-topic quiz score analysis."""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.models import QuizResult, SyllabusTopic, TopicLevel, User
from src.quiz.analysis import analyze_quiz_results


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _topic(db, user_id, name):
    topic = SyllabusTopic(
        id=uuid.uuid4(), user_id=user_id, document_id=uuid.uuid4(),
        name=name, level=TopicLevel.topic,
    )
    db.add(topic)
    return topic


def test_groups_scores_by_topic_and_flags_weak_areas(db_session):
    user = User(id=uuid.uuid4(), email="analysis@example.com", hashed_password="x")
    quiz_id = uuid.uuid4()
    weak = _topic(db_session, user.id, "Fractions")
    strong = _topic(db_session, user.id, "Geometry")
    other_quiz_topic = _topic(db_session, user.id, "Algebra")
    db_session.add(user)
    db_session.add_all([
        QuizResult(user_id=user.id, topic_id=weak.id, quiz_id=quiz_id, question="q1", score=0.2),
        QuizResult(user_id=user.id, topic_id=weak.id, quiz_id=quiz_id, question="q2", score=0.4),
        QuizResult(user_id=user.id, topic_id=strong.id, quiz_id=quiz_id, question="q3", score=1.0),
        QuizResult(user_id=user.id, topic_id=other_quiz_topic.id, quiz_id=uuid.uuid4(), question="q4", score=0.0),
    ])
    db_session.commit()

    analysis = analyze_quiz_results(db_session, user.id, quiz_id)

    assert analysis.total_questions == 3
    assert analysis.graded_questions == 3
    assert analysis.average_score == pytest.approx((0.2 + 0.4 + 1.0) / 3)
    assert [(topic.topic_name, topic.is_weak) for topic in analysis.topics] == [
        ("Fractions", True), ("Geometry", False),
    ]
    assert analysis.topics[0].average_score == pytest.approx(0.3)


def test_ungraded_topic_is_visible_but_not_flagged_weak(db_session):
    user = User(id=uuid.uuid4(), email="ungraded@example.com", hashed_password="x")
    quiz_id = uuid.uuid4()
    topic = _topic(db_session, user.id, "Kinematics")
    db_session.add(user)
    db_session.add(QuizResult(user_id=user.id, topic_id=topic.id, quiz_id=quiz_id, question="q"))
    db_session.commit()

    analysis = analyze_quiz_results(db_session, user.id, quiz_id)

    assert analysis.graded_questions == 0
    assert analysis.average_score is None
    assert analysis.topics[0].average_score is None
    assert analysis.topics[0].is_weak is False


def test_quiz_analysis_is_user_scoped_and_rejects_missing_quiz(db_session):
    owner = User(id=uuid.uuid4(), email="owner@example.com", hashed_password="x")
    stranger = User(id=uuid.uuid4(), email="stranger@example.com", hashed_password="x")
    quiz_id = uuid.uuid4()
    topic = _topic(db_session, owner.id, "Biology")
    db_session.add_all([owner, stranger])
    db_session.add(QuizResult(user_id=owner.id, topic_id=topic.id, quiz_id=quiz_id, question="q", score=1.0))
    db_session.commit()

    with pytest.raises(ValueError, match="Quiz not found"):
        analyze_quiz_results(db_session, stranger.id, quiz_id)


def test_analysis_endpoint_returns_topic_breakdown():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.auth.dependencies import get_current_user_id
    from src.db.session import get_db
    from src.quiz.router import router as quiz_router

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    user = User(id=uuid.uuid4(), email="endpoint@example.com", hashed_password="x")
    user_id = user.id
    other_user_id = uuid.uuid4()
    other_user = User(id=other_user_id, email="other@example.com", hashed_password="x")
    quiz_id = uuid.uuid4()
    db = session_factory()
    topic = _topic(db, user.id, "Electricity")
    topic_id = topic.id
    db.add_all([user, other_user])
    db.add(QuizResult(user_id=user.id, topic_id=topic.id, quiz_id=quiz_id, question="q", score=0.25))
    db.commit()
    db.close()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(quiz_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    response = TestClient(app).get(f"/quiz/{quiz_id}/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["average_score"] == 0.25
    assert payload["topics"] == [{
        "topic_id": str(topic_id),
        "topic_name": "Electricity",
        "questions_total": 1,
        "questions_answered": 1,
        "average_score": 0.25,
        "is_weak": True,
    }]

    app.dependency_overrides[get_current_user_id] = lambda: other_user_id
    forbidden_response = TestClient(app).get(f"/quiz/{quiz_id}/analysis")

    assert forbidden_response.status_code == 404
