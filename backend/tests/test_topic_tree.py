"""Tests for backend/src/topic_tree/ — P2-SHI4 topic-tree extraction and validation."""

import json
from unittest.mock import MagicMock

import pytest

from src.topic_tree import TopicTreeResponse, extract_topic_tree


def _make_mock_message(content_text: str):
    """Helper to construct a mock Anthropic message response."""
    mock_content = MagicMock()
    mock_content.text = content_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


class TestExtractTopicTree:

    def test_extract_topic_tree_success(self):
        """Feed a realistic syllabus text, mock valid LLM JSON response, assert schema validation and mastery=None."""
        syllabus_text = """
        Physics 101 Course Syllabus:
        Unit 1: Mechanics. Topics include Kinematics (subtopics: Vectors, Motion in 1D, Projectile Motion)
        and Newton's Laws (subtopics: First Law, Second Law, Third Law).
        Unit 2: Electromagnetism. Topics include Electrostatics (subtopics: Coulomb's Law, Electric Fields)
        and Magnetism (subtopics: Magnetic Fields, Lorentz Force).
        """

        mock_json_response = {
            "subject": "Physics",
            "units": [
                {
                    "name": "Mechanics",
                    "topics": [
                        {
                            "name": "Kinematics",
                            "subtopics": ["Vectors", "Motion in 1D", "Projectile Motion"],
                            "mastery": None,
                        },
                        {
                            "name": "Newton's Laws",
                            "subtopics": ["First Law", "Second Law", "Third Law"],
                            "mastery": None,
                        },
                    ],
                },
                {
                    "name": "Electromagnetism",
                    "topics": [
                        {
                            "name": "Electrostatics",
                            "subtopics": ["Coulomb's Law", "Electric Fields"],
                            "mastery": None,
                        },
                        {
                            "name": "Magnetism",
                            "subtopics": ["Magnetic Fields", "Lorentz Force"],
                            "mastery": None,
                        },
                    ],
                },
            ],
        }

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_message(
            json.dumps(mock_json_response)
        )

        result = extract_topic_tree(syllabus_text, client=mock_client)

        # Assert output validates against TopicTreeResponse Pydantic model
        validated_tree = TopicTreeResponse.model_validate(result)
        assert validated_tree.subject == "Physics"
        assert len(validated_tree.units) == 2
        assert validated_tree.units[0].name == "Mechanics"
        assert validated_tree.units[1].name == "Electromagnetism"

        # Assert every topic's mastery is None
        for unit in validated_tree.units:
            for topic in unit.topics:
                assert topic.mastery is None

    def test_extract_topic_tree_retry_recovery(self):
        """Mock LLM to return malformed JSON once, then valid JSON on retry; assert it recovers."""
        syllabus_text = "Chemistry Syllabus: Unit 1 Organic Chem, Topic Hydrocarbons"

        valid_json_response = {
            "subject": "Chemistry",
            "units": [
                {
                    "name": "Organic Chemistry",
                    "topics": [
                        {
                            "name": "Hydrocarbons",
                            "subtopics": ["Alkanes", "Alkenes"],
                            "mastery": None,
                        }
                    ],
                }
            ],
        }

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _make_mock_message("{invalid_json_text..."),  # 1st attempt fails
            _make_mock_message(json.dumps(valid_json_response)),  # 2nd attempt succeeds
        ]

        result = extract_topic_tree(syllabus_text, client=mock_client)

        assert mock_client.messages.create.call_count == 2
        assert result["subject"] == "Chemistry"
        assert result["units"][0]["topics"][0]["mastery"] is None

    def test_extract_topic_tree_forces_non_null_mastery_to_none(self):
        """Mock LLM returning a non-null mastery value, assert it gets forced to None."""
        syllabus_text = "Biology Syllabus: Unit 1 Genetics, Topic DNA"

        hallucinated_json_response = {
            "subject": "Biology",
            "units": [
                {
                    "name": "Genetics",
                    "topics": [
                        {
                            "name": "DNA Structure",
                            "subtopics": ["Double Helix", "Base Pairs"],
                            "mastery": 0.85,  # Hallucinated non-null value
                        }
                    ],
                }
            ],
        }

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_message(
            json.dumps(hallucinated_json_response)
        )

        result = extract_topic_tree(syllabus_text, client=mock_client)

        # Assert post-parse safety net forced mastery to None
        assert result["units"][0]["topics"][0]["mastery"] is None
        validated_tree = TopicTreeResponse.model_validate(result)
        assert validated_tree.units[0].topics[0].mastery is None

    def test_extract_topic_tree_raises_after_failed_retry(self):
        """Assert ValueError is raised if retry also fails validation."""
        syllabus_text = "Math Syllabus"

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _make_mock_message("NOT JSON"),
            _make_mock_message("STILL NOT JSON"),
        ]

        with pytest.raises(ValueError, match="Failed to extract topic tree after retry"):
            extract_topic_tree(syllabus_text, client=mock_client)
