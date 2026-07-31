"""Tests for backend/src/diagnostic/ — P3-SRE6 diagnostic question generation."""

import json
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel, User
from src.diagnostic import generate_diagnostic_questions, create_diagnostic_session
from src.diagnostic.generator import DEFAULT_MAX_QUESTIONS


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


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

    def test_raises_after_failed_retry(self):
        """Assert ValueError is raised if both attempts fail validation."""
        mock_client = MagicMock()
        mock_client.chat.side_effect = [
            _make_mock_message("NOT JSON"),
            _make_mock_message("STILL NOT JSON"),
        ]

        with pytest.raises(ValueError, match="Failed to generate diagnostic questions"):
            generate_diagnostic_questions(["Some Topic"], client=mock_client)


class TestCreateDiagnosticSession:
    def test_persists_session_and_links_topics(self, db_session):
        """Persist a question set; assert a Session row and matching ChatMessage rows are created,
        with topic_reference_id correctly linked to existing syllabus_topics rows."""
        user = User(
            id=uuid.uuid4(),
            email="student@example.com",
            hashed_password="hashed",
            name="Test Student",
        )
        doc = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="notes.pdf",
            storage_path="/uploads/notes.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        topic = SyllabusTopic(
            id=uuid.uuid4(),
            user_id=user.id,
            document_id=doc.id,
            parent_id=None,
            name="Kinematics",
            level=TopicLevel.topic,
        )
        db_session.add_all([user, doc, topic])
        db_session.commit()

        questions = [
            {
                "topic_name": "Kinematics",
                "question_type": "mcq",
                "question_text": "What is velocity?",
                "options": ["Speed", "Rate of displacement", "Force", "Mass"],
                "correct_answer": "Rate of displacement",
            }
        ]

        session, messages = create_diagnostic_session(db_session, user.id, doc.id, questions)

        assert session.type.value == "diagnostic"
        assert len(messages) == 1
        assert messages[0].topic_reference_id == topic.id

        stored_content = json.loads(messages[0].content)
        assert stored_content["correct_answer"] == "Rate of displacement"

    def test_falls_back_to_none_when_topic_not_found(self, db_session):
        """If a question's topic_name doesn't match any syllabus_topics row, topic_reference_id is None
        rather than raising — an LLM typo shouldn't crash the whole request."""
        user = User(
            id=uuid.uuid4(),
            email="student2@example.com",
            hashed_password="hashed",
            name="Test Student 2",
        )
        doc = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="notes2.pdf",
            storage_path="/uploads/notes2.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        db_session.add_all([user, doc])
        db_session.commit()

        questions = [
            {
                "topic_name": "Nonexistent Topic",
                "question_type": "short_answer",
                "question_text": "Some question?",
                "options": None,
                "correct_answer": "Some answer",
            }
        ]

        session, messages = create_diagnostic_session(db_session, user.id, doc.id, questions)

        assert messages[0].topic_reference_id is None