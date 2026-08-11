import time
import uuid

from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import User
from src.scheduling import (
    SchedulePlan,
    ScheduleRequest,
    build_schedule,
    get_current_schedule,
    get_schedule_history,
    get_schedule_version,
    persist_schedule,
)


def test_build_schedule_prioritizes_weak_topics_and_respects_daily_hours():
    request = ScheduleRequest(
        topics=[
            {"id": "t1", "title": "Fractions", "mastery": 0.2, "estimated_hours": 2},
            {"id": "t2", "title": "Geometry", "mastery": 0.4, "estimated_hours": 1},
            {"id": "t3", "title": "Algebra", "mastery": 0.8, "estimated_hours": 1},
        ],
        hours_per_day=2,
    )

    plan = build_schedule(request)

    assert plan.days
    assert plan.days[0].topics[0].title == "Fractions"
    assert plan.days[1].topics[0].title == "Geometry"
    assert plan.days[0].topics[0].mastery == 0.2
    assert all(
        sum(topic.estimated_hours for topic in day.topics) <= request.hours_per_day
        for day in plan.days
    )


def test_build_schedule_uses_exam_date_to_create_day_labels():
    from datetime import date, timedelta

    request = ScheduleRequest(
        topics=[
            {"id": str(uuid.uuid4()), "title": "Biology", "mastery": 0.3, "estimated_hours": 1},
        ],
        hours_per_day=1,
        exam_date=date.today() + timedelta(days=2),
    )

    plan = build_schedule(request)

    assert len(plan.days) == 3
    assert plan.days[0].label == date.today().strftime("%Y-%m-%d")
    assert plan.days[-1].label == (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")


def test_build_schedule_adds_an_overflow_day_when_exam_window_is_full():
    from datetime import date, timedelta

    request = ScheduleRequest(
        topics=[
            {"id": "t1", "title": "Fractions", "mastery": 0.2, "estimated_hours": 2},
            {"id": "t2", "title": "Geometry", "mastery": 0.4, "estimated_hours": 1},
        ],
        hours_per_day=2,
        exam_date=date.today(),
    )

    plan = build_schedule(request)

    assert len(plan.days) == 2
    assert all(
        sum(topic.estimated_hours for topic in day.topics) <= request.hours_per_day
        for day in plan.days
    )
    assert plan.days[1].topics[0].title == "Geometry"
    assert plan.days[1].label == "Day 2 (past exam date — plan exceeds available time)"


def test_persisted_schedules_are_versioned_and_retrievable():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user_id = uuid.uuid4()
    db.add(User(id=user_id, email="schedule@example.com", hashed_password="hashed"))
    db.commit()

    first_plan = SchedulePlan.model_validate(
        {"days": [{"label": "Day 1", "topics": []}]}
    )
    second_plan = SchedulePlan.model_validate(
        {"days": [{"label": "Day 1", "topics": []}, {"label": "Day 2", "topics": []}]}
    )

    import time

    first_version = persist_schedule(db, user_id, first_plan)
    time.sleep(0.01)
    second_version = persist_schedule(db, user_id, second_plan)


    current = get_current_schedule(db, user_id)
    history = get_schedule_history(db, user_id)
    retrieved_first = get_schedule_version(db, user_id, first_version.version_id)

    assert current is not None
    assert current.version_id == second_version.version_id
    assert current.plan == second_plan
    assert [version.version_id for version in history] == [
        second_version.version_id,
        first_version.version_id,
    ]
    assert retrieved_first is not None
    assert retrieved_first.version_id == first_version.version_id
    assert retrieved_first.plan == first_plan


def test_schedule_http_endpoints():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from src.auth.dependencies import get_current_user_id
    from src.db.session import get_db
    from src.scheduling.routes import router as scheduling_router

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    test_user_id = uuid.uuid4()
    init_db = TestingSessionLocal()
    init_db.add(User(id=test_user_id, email="route_test@example.com", hashed_password="pw"))
    init_db.commit()
    init_db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(scheduling_router)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = lambda: test_user_id

    client = TestClient(app)

    # GET /schedules/current when empty -> 404
    resp = client.get("/schedules/current")
    assert resp.status_code == 404

    # POST /schedules -> 201
    post_payload = {
        "topics": [{"id": "t1", "title": "Calculus", "mastery": 0.3, "estimated_hours": 2}],
        "hours_per_day": 2,
    }
    create_resp = client.post("/schedules", json=post_payload)
    assert create_resp.status_code == 201
    v1_data = create_resp.json()
    assert "version_id" in v1_data
    v1_id = v1_data["version_id"]

    # POST /schedules again to create v2
    time.sleep(0.01)
    create_resp2 = client.post("/schedules", json=post_payload)

    assert create_resp2.status_code == 201
    v2_data = create_resp2.json()
    v2_id = v2_data["version_id"]

    # GET /schedules/current -> returns v2
    curr_resp = client.get("/schedules/current")
    assert curr_resp.status_code == 200
    assert curr_resp.json()["version_id"] == v2_id

    # GET /schedules/history -> returns [v2, v1]
    hist_resp = client.get("/schedules/history")
    assert hist_resp.status_code == 200
    hist_ids = [item["version_id"] for item in hist_resp.json()]
    assert hist_ids == [v2_id, v1_id]

    # GET /schedules/{v1_id} -> returns v1
    v1_resp = client.get(f"/schedules/{v1_id}")
    assert v1_resp.status_code == 200
    assert v1_resp.json()["version_id"] == v1_id

    # GET /schedules/{random_id} -> 404
    random_id = str(uuid.uuid4())
    notFound_resp = client.get(f"/schedules/{random_id}")
    assert notFound_resp.status_code == 404


def test_schedule_user_isolation():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from src.auth.dependencies import get_current_user_id
    from src.db.session import get_db
    from src.scheduling.routes import router as scheduling_router

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    db = TestingSessionLocal()
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    db.add(User(id=user_a_id, email="usera@example.com", hashed_password="pw"))
    db.add(User(id=user_b_id, email="userb@example.com", hashed_password="pw"))
    db.commit()

    # Persist schedule for user A
    plan_a = SchedulePlan.model_validate(
        {"days": [{"label": "Day 1", "topics": []}]}
    )
    version_a = persist_schedule(db, user_a_id, plan_a)

    # As user B, call persistence functions directly
    assert get_current_schedule(db, user_b_id) is None
    assert get_schedule_history(db, user_b_id) == []
    assert get_schedule_version(db, user_b_id, version_a.version_id) is None

    # Equivalent check via HTTP test client as user B
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(scheduling_router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = lambda: user_b_id

    client = TestClient(app)

    # User B requests current schedule -> 404
    assert client.get("/schedules/current").status_code == 404

    # User B requests schedule history -> []
    history_resp = client.get("/schedules/history")
    assert history_resp.status_code == 200
    assert history_resp.json() == []

    # User B requests User A's version_id -> 404
    assert client.get(f"/schedules/{version_a.version_id}").status_code == 404


