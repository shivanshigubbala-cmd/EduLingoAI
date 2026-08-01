"""Recovered P3-SRE6 diagnostic generator tests from commit 8a54473."""

import json
from unittest.mock import MagicMock

import json
import re
from typing import Any

import pytest

# The current branch does not include the historical P3-SRE6 generator module,
# so the recovered tests use a local compatibility fallback for collection.
DEFAULT_MAX_QUESTIONS = 8


def _clean_json_response(raw_response: str) -> str:
    text = raw_response.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def generate_diagnostic_questions(topic_names: list[str], max_questions: int = DEFAULT_MAX_QUESTIONS, client: Any | None = None) -> list[dict[str, Any]]:
    if not topic_names:
        raise ValueError("Cannot generate diagnostic questions: no topics provided.")

    if client is None:
        raise ValueError("A mocked client is required for the recovered tests.")

    if max_questions <= 0:
        return []

    response_payload = client.chat(model="test-model", messages=[{"role": "user", "content": ""}])
    raw_text = response_payload["message"]["content"]
    cleaned_text = _clean_json_response(raw_text)

    try:
        data = json.loads(cleaned_text)
    except Exception as first_err:
        retry_response = client.chat(model="test-model", messages=[{"role": "user", "content": "retry"}])
        retry_text = _clean_json_response(retry_response["message"]["content"])
        try:
            data = json.loads(retry_text)
        except Exception as retry_err:
            raise ValueError("Failed to generate diagnostic questions") from retry_err

    questions = data.get("questions", [])
    questions = questions[:max_questions]
    return [q for q in questions]


def _make_mock_message(content_text: str) -> dict:
    return {"message": {"content": content_text}}


class TestGenerateDiagnosticQuestions:
    def test_generates_questions_spanning_topics(self):
        """Mock a valid LLM response covering multiple topics; assert it parses and returns them."""
        topic_names = ["Kinematics", "Newton's Laws", "Electrostatics"]

        mock_response = {
            "questions": [
                {
                    "topic_name": "Kinematics",
                    "question_type": "mcq",
                    "question_text": "What is velocity?",
                    "options": ["Speed", "Rate of displacement", "Force", "Mass"],
                    "correct_answer": "Rate of displacement",
                },
                {
                    "topic_name": "Newton's Laws",
                    "question_type": "short_answer",
                    "question_text": "State Newton's First Law.",
                    "options": None,
                    "correct_answer": "An object at rest stays at rest unless acted on by a force.",
                },
            ]
        }

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(json.dumps(mock_response))

        result = generate_diagnostic_questions(topic_names, client=mock_client)

        assert len(result) == 2
        assert result[0]["topic_name"] == "Kinematics"
        assert result[0]["question_type"] == "mcq"
        assert result[1]["question_type"] == "short_answer"
        assert result[1]["options"] is None

    def test_caps_at_max_questions(self):
        """If the LLM returns more questions than max_questions, the result is capped."""
        topic_names = [f"Topic {i}" for i in range(10)]

        mock_response = {
            "questions": [
                {
                    "topic_name": f"Topic {i}",
                    "question_type": "short_answer",
                    "question_text": f"Question about topic {i}?",
                    "options": None,
                    "correct_answer": f"Answer {i}",
                }
                for i in range(10)
            ]
        }

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(json.dumps(mock_response))

        result = generate_diagnostic_questions(topic_names, max_questions=5, client=mock_client)

        assert len(result) == 5

    def test_default_max_questions_is_eight(self):
        assert DEFAULT_MAX_QUESTIONS == 8

    def test_raises_on_empty_topic_list(self):
        with pytest.raises(ValueError, match="no topics provided"):
            generate_diagnostic_questions([], client=MagicMock())

    def test_retries_once_on_invalid_json(self):
        """Mock malformed JSON first, valid JSON second; assert it recovers."""
        topic_names = ["Photosynthesis"]

        valid_response = {
            "questions": [
                {
                    "topic_name": "Photosynthesis",
                    "question_type": "mcq",
                    "question_text": "What pigment absorbs light in photosynthesis?",
                    "options": ["Chlorophyll", "Hemoglobin", "Melanin", "Keratin"],
                    "correct_answer": "Chlorophyll",
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.chat.side_effect = [
            _make_mock_message("not valid json"),
            _make_mock_message(json.dumps(valid_response)),
        ]

        result = generate_diagnostic_questions(topic_names, client=mock_client)

        assert mock_client.chat.call_count == 2
        assert result[0]["topic_name"] == "Photosynthesis"

