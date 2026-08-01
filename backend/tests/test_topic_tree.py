"""Tests for backend/src/topic_tree/ — P2-SHI4 topic-tree extraction and P2-SHI5 topic-tree persistence."""

import json
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel, User
from src.topic_tree import (
    TopicTreeResponse,
    extract_topic_tree,
    get_topic_tree,
    persist_topic_tree,
)


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
    """Helper to construct a mock Ollama chat() response."""
    return {"message": {"content": content_text}}


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
        mock_client.chat.return_value = _make_mock_message(
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
        mock_client.chat.side_effect = [
            _make_mock_message("{invalid_json_text..."),  # 1st attempt fails
            _make_mock_message(json.dumps(valid_json_response)),  # 2nd attempt succeeds
        ]

        result = extract_topic_tree(syllabus_text, client=mock_client)

        assert mock_client.chat.call_count == 2
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
        mock_client.chat.return_value = _make_mock_message(
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
        mock_client.chat.side_effect = [
            _make_mock_message("NOT JSON"),
            _make_mock_message("STILL NOT JSON"),
        ]

        with pytest.raises(ValueError, match="Failed to extract topic tree after retry"):
            extract_topic_tree(syllabus_text, client=mock_client)


class TestTopicTreePersistence:

    def test_persist_and_retrieve_topic_tree_roundtrip(self, db_session):
        """Build sample tree, persist to DB, query back by user_id + document_id, assert match."""
        # 1. Setup User and Document records in SQLite
        user = User(
            id=uuid.uuid4(),
            email="testuser@example.com",
            hashed_password="hashed_pass_secret",
            name="Test User",
        )
        doc = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="syllabus.pdf",
            storage_path="/uploads/syllabus.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        db_session.add_all([user, doc])
        db_session.commit()

        # 2. Sample topic tree matching P2-SHI4 structure
        sample_tree = {
            "subject": "Computer Science",
            "units": [
                {
                    "name": "Data Structures",
                    "topics": [
                        {
                            "name": "Arrays & Lists",
                            "subtopics": ["Dynamic Arrays", "Linked Lists"],
                            "mastery": None,
                        },
                        {
                            "name": "Trees & Graphs",
                            "subtopics": ["Binary Search Trees", "DFS & BFS"],
                            "mastery": None,
                        },
                    ],
                },
                {
                    "name": "Algorithms",
                    "topics": [
                        {
                            "name": "Sorting",
                            "subtopics": ["Quicksort", "Mergesort"],
                            "mastery": None,
                        }
                    ],
                },
            ],
        }

        # 3. Persist topic tree
        persisted_rows = persist_topic_tree(
            db_session,
            user_id=user.id,
            document_id=doc.id,
            tree=sample_tree,
        )

        # Expected row breakdown:
        # 1 subject + 2 units + 3 topics + 6 subtopics = 12 total rows
        assert len(persisted_rows) == 12

        # Assert level enum distribution in database
        db_topics = (
            db_session.query(SyllabusTopic)
            .filter_by(user_id=user.id, document_id=doc.id)
            .all()
        )
        assert len(db_topics) == 12

        subjects = [t for t in db_topics if t.level == TopicLevel.subject]
        units = [t for t in db_topics if t.level == TopicLevel.unit]
        topics = [t for t in db_topics if t.level == TopicLevel.topic]
        subtopics = [t for t in db_topics if t.level == TopicLevel.subtopic]

        assert len(subjects) == 1
        assert len(units) == 2
        assert len(topics) == 3
        assert len(subtopics) == 6

        # Assert parent_id links
        subject_id = subjects[0].id
        for u in units:
            assert u.parent_id == subject_id
        for t in topics:
            assert t.parent_id in [u.id for u in units]
        for st in subtopics:
            assert st.parent_id in [t.id for t in topics]

        # 4. Retrieve topic tree back from DB
        reconstructed_tree = get_topic_tree(
            db_session,
            user_id=user.id,
            document_id=doc.id,
        )

        # 5. Roundtrip Assertion: reconstructed tree matches sample tree
        assert reconstructed_tree == sample_tree

    def test_get_topic_tree_returns_none_when_empty(self, db_session):
        """Querying get_topic_tree for non-existent user_id/document_id returns None."""
        res = get_topic_tree(db_session, user_id=uuid.uuid4(), document_id=uuid.uuid4())
        assert res is None