"""Tests for P6-SHR9 — auto-grading logic.

MCQ grading is pure logic (no LLM), tested directly. Short-answer grading
uses a mocked Ollama client, same pattern as test_quiz_generator.py.
"""
import json
from unittest.mock import MagicMock

from src.quiz.grading import grade_answer, grade_mcq, grade_short_answer


def _make_mock_message(content_text: str) -> dict:
    return {"message": {"content": content_text}}


class TestGradeMCQ:
    def test_exact_match_is_correct(self):
        result = grade_mcq("Paris", "Paris")
        assert result["is_correct"] is True
        assert result["score"] == 1.0

    def test_case_insensitive_match(self):
        result = grade_mcq("Paris", "paris")
        assert result["is_correct"] is True

    def test_whitespace_trimmed(self):
        result = grade_mcq("Paris", "  Paris  ")
        assert result["is_correct"] is True

    def test_wrong_answer_is_incorrect(self):
        result = grade_mcq("Paris", "London")
        assert result["is_correct"] is False
        assert result["score"] == 0.0

    def test_no_partial_credit_for_close_but_wrong(self):
        """MCQ options are selected verbatim — no fuzzy matching."""
        result = grade_mcq("Paris, France", "Paris")
        assert result["is_correct"] is False


class TestGradeShortAnswer:
    def test_full_credit_response(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            json.dumps({"score": 1.0, "rationale": "Fully correct and complete."})
        )

        result = grade_short_answer(
            "What causes seasons?",
            "Earth's axial tilt",
            "Earth is tilted on its axis",
            client=mock_client,
        )

        assert result["score"] == 1.0
        assert result["is_correct"] is True
        assert "rationale" in result

    def test_partial_credit_response(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            json.dumps({"score": 0.3, "rationale": "Mostly missing the key concept."})
        )

        result = grade_short_answer(
            "Explain photosynthesis.",
            "Plants convert light to chemical energy using chlorophyll",
            "I don't really know",
            client=mock_client,
        )

        assert result["score"] == 0.3
        assert result["is_correct"] is False  # below the 0.5 threshold

    def test_score_clamped_to_valid_range(self):
        """A misbehaving LLM returning score > 1.0 shouldn't corrupt the result."""
        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            json.dumps({"score": 1.5, "rationale": "Great answer."})
        )

        result = grade_short_answer("Q", "A", "student answer", client=mock_client)

        assert result["score"] == 1.0

    def test_invalid_json_falls_back_gracefully(self):
        """A grading failure shouldn't crash the request — defaults to 0."""
        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message("not valid json at all")

        result = grade_short_answer("Q", "A", "student answer", client=mock_client)

        assert result["score"] == 0.0
        assert result["is_correct"] is None
        assert "Grading failed" in result["rationale"]

    def test_missing_score_field_falls_back_gracefully(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            json.dumps({"rationale": "Forgot to include a score."})
        )

        result = grade_short_answer("Q", "A", "student answer", client=mock_client)

        assert result["score"] == 0.0
        assert result["is_correct"] is None


class TestGradeAnswerDispatch:
    def test_mcq_routes_to_exact_match(self):
        result = grade_answer("mcq", "irrelevant question text", "4", "4")
        assert result["is_correct"] is True
        assert result["score"] == 1.0

    def test_short_answer_routes_to_llm_rubric(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            json.dumps({"score": 0.8, "rationale": "Mostly correct."})
        )

        result = grade_answer(
            "short_answer", "Explain X.", "the correct explanation", "a decent attempt",
            client=mock_client,
        )

        assert result["score"] == 0.8
        mock_client.chat.assert_called_once()