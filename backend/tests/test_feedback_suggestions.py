"""P7-SHI12 proactive check-in suggestion tests."""

from src.db.models import FeedbackSuggestion
from src.feedback import apply_quiz_feedback, complete_schedule_day, get_active_suggestions
from src.scheduling.persistence import persist_schedule
from src.scheduling.schemas import SchedulePlan

from test_feedback import _seed_quiz, _session


def test_completed_quiz_creates_one_suggestion_for_each_weak_covered_topic():
    db = _session()
    user, _document, now_weak, initially_weak, quiz_id = _seed_quiz(db)

    assert apply_quiz_feedback(db, user.id, quiz_id) is not None
    suggestions = get_active_suggestions(db, user.id)

    assert [(item.topic_id, item.trigger, item.action) for item in suggestions] == [
        (now_weak.id, "quiz", "quiz")
    ]
    assert now_weak.name in suggestions[0].message
    assert initially_weak.id not in [item.topic_id for item in suggestions]

    assert apply_quiz_feedback(db, user.id, quiz_id) is None
    assert db.query(FeedbackSuggestion).filter_by(user_id=user.id).count() == 1


def test_completed_schedule_day_creates_one_idempotent_check_in_suggestion():
    db = _session()
    user, _document, now_weak, _initially_weak, _quiz_id = _seed_quiz(db)
    plan = SchedulePlan.model_validate(
        {
            "days": [
                {
                    "label": "Day 1",
                    "topics": [
                        {
                            "id": str(now_weak.id),
                            "title": now_weak.name,
                            "mastery": now_weak.mastery,
                        }
                    ],
                }
            ]
        }
    )
    version = persist_schedule(db, user.id, plan)

    first = complete_schedule_day(db, user.id, version.version_id, 0)
    second = complete_schedule_day(db, user.id, version.version_id, 0)

    assert first.id == second.id
    suggestions = get_active_suggestions(db, user.id)
    assert len(suggestions) == 1
    assert suggestions[0].topic_id == now_weak.id
    assert suggestions[0].trigger == "schedule_milestone"


def test_completed_schedule_day_creates_reinforcement_check_in_regardless_of_mastery():
    import uuid
    from src.db.models import SyllabusTopic, TopicLevel

    db = _session()
    user, _document, now_weak, _initially_weak, _quiz_id = _seed_quiz(db)

    strong_topic = SyllabusTopic(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=now_weak.document_id,
        name="Strong Topic",
        level=TopicLevel.topic,
        mastery=0.8,
    )
    db.add(strong_topic)
    db.commit()

    plan = SchedulePlan.model_validate(
        {
            "days": [
                {
                    "label": "Day 1",
                    "topics": [
                        {"id": str(strong_topic.id), "title": strong_topic.name, "mastery": 0.8}
                    ],
                }
            ]
        }
    )
    version = persist_schedule(db, user.id, plan)
    complete_schedule_day(db, user.id, version.version_id, 0)

    suggestions = get_active_suggestions(db, user.id)
    assert len(suggestions) == 1
    assert suggestions[0].topic_id == strong_topic.id
    assert suggestions[0].trigger == "schedule_milestone"



def test_feedback_routes_cross_user_isolation():
    import uuid
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from src.auth.dependencies import get_current_user_id
    from src.db.base import Base
    from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel, User
    from src.db.session import get_db
    from src.feedback.routes import router as feedback_router
    from src.scheduling.routes import router as scheduling_router

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    db = TestingSessionLocal()
    user_a = User(id=uuid.uuid4(), email="usera@example.com", hashed_password="pw")
    user_b = User(id=uuid.uuid4(), email="userb@example.com", hashed_password="pw")
    db.add_all([user_a, user_b])
    db.commit()

    doc_a = Document(
        id=uuid.uuid4(),
        user_id=user_a.id,
        filename="doc.pdf",
        storage_path="/tmp/doc.pdf",
        mime_type="application/pdf",
        status=DocumentStatus.parsed,
    )
    db.add(doc_a)
    db.commit()

    topic_a = SyllabusTopic(
        id=uuid.uuid4(),
        user_id=user_a.id,
        document_id=doc_a.id,
        name="Topic A",
        level=TopicLevel.topic,
        mastery=0.2,
    )
    db.add(topic_a)
    db.commit()

    plan_a = SchedulePlan.model_validate(
        {
            "days": [
                {
                    "label": "Day 1",
                    "topics": [{"id": str(topic_a.id), "title": topic_a.name, "mastery": 0.2}],
                }
            ]
        }
    )
    version_a = persist_schedule(db, user_a.id, plan_a)
    complete_schedule_day(db, user_a.id, version_a.version_id, 0)
    suggestions_a = get_active_suggestions(db, user_a.id)
    assert len(suggestions_a) == 1
    suggestion_a_id = suggestions_a[0].id

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(scheduling_router)
    app.include_router(feedback_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = lambda: user_b.id

    client = TestClient(app)

    # 1. User B tries to complete User A's schedule day -> 404
    resp_complete = client.post(f"/schedules/{version_a.version_id}/days/0/complete")
    assert resp_complete.status_code == 404

    # 2. User B lists suggestions -> returns [] (does not see User A's suggestion)
    resp_list = client.get("/feedback/suggestions")
    assert resp_list.status_code == 200
    assert resp_list.json() == []

    # 3. User B tries to dismiss User A's suggestion -> 404
    resp_dismiss = client.post(f"/feedback/suggestions/{suggestion_a_id}/dismiss")
    assert resp_dismiss.status_code == 404

