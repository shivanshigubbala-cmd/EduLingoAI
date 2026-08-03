"""Tests for backend/src/scheduling/explain.py — P4-SRE8 schedule explanation."""

from unittest.mock import MagicMock

import pytest

from src.scheduling.explain import generate_schedule_explanation
from src.scheduling.schemas import ScheduleDay, SchedulePlan, TopicPlanItem


def _make_mock_message(content_text: str) -> dict:
    return {"message": {"content": content_text}}


class TestGenerateScheduleExplanation:
    def test_generates_explanation_referencing_real_topics(self):
        plan = SchedulePlan(
            days=[
                ScheduleDay(
                    label="Day 1",
                    topics=[
                        TopicPlanItem(id="t1", title="Kinematics", mastery=0.2, estimated_hours=2),
                    ],
                ),
                ScheduleDay(
                    label="Day 2",
                    topics=[
                        TopicPlanItem(id="t2", title="Optics", mastery=0.9, estimated_hours=1),
                    ],
                ),
            ]
        )

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            "Since Kinematics has a lower mastery score (0.20), it's scheduled first "
            "so you can strengthen it early. Optics, at 0.90 mastery, comes later "
            "since you're already comfortable with it. You've got this!"
        )

        result = generate_schedule_explanation(plan, client=mock_client)

        assert "Kinematics" in result
        assert len(result) > 0
        mock_client.chat.assert_called_once()

    def test_raises_on_empty_schedule(self):
        empty_plan = SchedulePlan(days=[])
        with pytest.raises(ValueError, match="empty schedule"):
            generate_schedule_explanation(empty_plan, client=MagicMock())

    def test_raises_when_llm_call_fails(self):
        plan = SchedulePlan(
            days=[
                ScheduleDay(
                    label="Day 1",
                    topics=[TopicPlanItem(id="t1", title="Algebra", mastery=0.3, estimated_hours=1)],
                )
            ]
        )
        mock_client = MagicMock()
        mock_client.chat.side_effect = RuntimeError("connection refused")

        with pytest.raises(ValueError, match="Failed to generate schedule explanation"):
            generate_schedule_explanation(plan, client=mock_client)