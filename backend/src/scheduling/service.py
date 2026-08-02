from __future__ import annotations

from datetime import date, timedelta

from src.scheduling.schemas import ScheduleDay, SchedulePlan, ScheduleRequest, TopicPlanItem


def build_schedule(request: ScheduleRequest) -> SchedulePlan:
    """Build a study plan that prioritizes weak topics first.

    The algorithm orders topics by mastery ascending, then allocates them to days
    while respecting the available study hours per day. If an exam date is given,
    the plan starts with one day per day between today and the exam date. Work
    that cannot fit in that window is placed on clearly labelled overflow days.
    """
    ordered_topics = sorted(
        request.topics,
        key=lambda topic: (topic.mastery, topic.estimated_hours, topic.title),
    )

    if not ordered_topics:
        return SchedulePlan(days=[])

    if request.exam_date is not None:
        start_day = date.today()
        end_day = request.exam_date
        if end_day < start_day:
            end_day = start_day
        day_count = max(1, (end_day - start_day).days + 1)
    else:
        day_count = max(1, len(ordered_topics))

    hours_per_day = max(1, request.hours_per_day)
    exam_day_count = day_count
    days: list[list[TopicPlanItem]] = [[] for _ in range(day_count)]
    current_day = 0

    for topic in ordered_topics:
        while (
            sum(item.estimated_hours for item in days[current_day])
            + topic.estimated_hours
            > hours_per_day
        ):
            current_day += 1
            if current_day == len(days):
                days.append([])
        days[current_day].append(topic)

    plan_days = []
    for index, topics in enumerate(days):
        if request.exam_date is not None and index < exam_day_count:
            day_label = (date.today() + timedelta(days=index)).strftime("%Y-%m-%d")
        elif request.exam_date is not None:
            day_label = f"Day {index + 1} (past exam date — plan exceeds available time)"
        else:
            day_label = f"Day {index + 1}"
        plan_days.append(ScheduleDay(label=day_label, topics=list(topics)))

    return SchedulePlan(days=plan_days)
