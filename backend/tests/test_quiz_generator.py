"""Tests for P6-SHR8 — quiz generator.

Covers the mastery-weighted allocation logic directly (no LLM needed —
this is pure math and is the actual acceptance criteria: "Quiz weights
questions toward topics with lower mastery scores"), plus the LLM-calling
path with a mocked Ollama client, following the same pattern as
test_diagnostic_generator.py.
"""
import json
import uuid
from unittest.mock import MagicMock

import pytest

from src.quiz.generator import allocate_question_counts, generate_quiz_questions


def _make_mock_message(content_text: str) -> dict:
    return {"message": {"content": content_text}}


class TestAllocateQuestionCounts:
    def test_weaker_topic_gets_more_questions(self):
        """The core acceptance criteria: lower mastery -> more questions."""
        topics = [
            {"id": uuid.uuid4(), "name": "Weak Topic", "mastery": 0.1},
            {"id": uuid.uuid4(), "name": "Strong Topic", "mastery": 0.9},
        ]
        counts = allocate_question_counts(topics, total_questions=10)

        assert counts["Weak Topic"] > counts["Strong Topic"]

    def test_total_always_sums_exactly(self):
        """Largest-remainder rounding must never drop or add a question."""
        topics = [
            {"id": uuid.uuid4(), "name": f"Topic {i}", "mastery": 0.1 * i}
            for i in range(7)
        ]
        counts = allocate_question_counts(topics, total_questions=10)

        assert sum(counts.values()) == 10

    def test_unscored_topic_gets_default_weight(self):
        """A topic with mastery=None shouldn't be treated as fully mastered."""
        topics = [
            {"id": uuid.uuid4(), "name": "Unscored", "mastery": None},
            {"id": uuid.uuid4(), "name": "Fully Mastered", "mastery": 1.0},
        ]
        counts = allocate_question_counts(topics, total_questions=10)

        assert counts["Unscored"] > counts["Fully Mastered"]

    def test_all_fully_mastered_falls_back_to_equal_split(self):
        """Zero total weight shouldn't crash or return an empty allocation."""
        topics = [
            {"id": uuid.uuid4(), "name": "A", "mastery": 1.0},
            {"id": uuid.uuid4(), "name": "B", "mastery": 1.0},
        ]
        counts = allocate_question_counts(topics, total_questions=10)

        assert sum(counts.values()) == 10
        assert counts["A"] == counts["B"]

    def test_empty_topics_returns_empty(self):
        assert allocate_question_counts([], total_questions=10) == {}

    def test_zero_questions_returns_empty(self):
        topics = [{"id": uuid.uuid4(), "name": "A", "mastery": 0.5}]
        assert allocate_question_counts(topics, total_questions=0) == {}


class TestGenerateQuizQuestions:
    def test_generates_questions_with_topic_ids_attached(self):
        weak_id = uuid.uuid4()
        topics = [{"id": weak_id, "name": "Weak Topic", "mastery": 0.1}]

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            json.dumps(
                {
                    "questions": [
                        {
                            "topic_name": "Weak Topic",
                            "question_type": "mcq",
                            "question_text": "What is 2+2?",
                            "options": ["3", "4", "5", "6"],
                            "correct_answer": "4",
                        }
                    ]
                }
            )
        )

        questions = generate_quiz_questions(topics, max_questions=1, client=mock_client)

        assert len(questions) == 1
        assert questions[0]["topic_id"] == weak_id
        assert questions[0]["correct_answer"] == "4"

    def test_empty_topics_raises_value_error(self):
        with pytest.raises(ValueError, match="no topics provided"):
            generate_quiz_questions([], client=MagicMock())

    def test_retries_once_on_invalid_json_then_succeeds(self):
        topics = [{"id": uuid.uuid4(), "name": "Topic A", "mastery": 0.5}]

        mock_client = MagicMock()
        mock_client.chat.side_effect = [
            _make_mock_message("not valid json"),
            _make_mock_message(
                json.dumps(
                    {
                        "questions": [
                            {
                                "topic_name": "Topic A",
                                "question_type": "short_answer",
                                "question_text": "Explain X.",
                                "options": None,
                                "correct_answer": "Because Y.",
                            }
                        ]
                    }
                )
            ),
        ]

        questions = generate_quiz_questions(topics, max_questions=1, client=mock_client)

        assert len(questions) == 1
        assert mock_client.chat.call_count == 2

    def test_raises_after_second_failed_attempt(self):
        topics = [{"id": uuid.uuid4(), "name": "Topic A", "mastery": 0.5}]

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message("still not valid json")

        with pytest.raises(ValueError, match="Failed to generate quiz questions"):
            generate_quiz_questions(topics, max_questions=1, client=mock_client)