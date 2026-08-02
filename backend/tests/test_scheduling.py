import uuid

from src.scheduling import ScheduleRequest, build_schedule


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
