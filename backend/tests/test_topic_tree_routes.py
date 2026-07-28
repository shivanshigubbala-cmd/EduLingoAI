"""Integration tests for backend/src/topic_tree/routes.py — P2-SHI4/5/6 HTTP routes."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.dependencies import get_current_user_id
from src.db.base import Base
from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel, User
from src.db.session import get_db
from src.main import app
from src.topic_tree import get_topic_tree, persist_topic_tree

_DEV_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
_OTHER_USER_ID = uuid.UUID("b0000000-0000-0000-0000-000000000002")


def _make_mock_message(content_text: str):
    mock_content = MagicMock()
    mock_content.text = content_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    def _override_get_user_id():
        return _DEV_USER_ID

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user_id] = _override_get_user_id
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestTopicTreeRoutes:

    @patch("anthropic.Anthropic")
    def test_post_extract_persists_and_returns_tree(self, mock_anthropic_cls, client, db_session):
        """POST /documents/{doc_id}/extract extracts, persists, and returns topic tree."""
        # 1. Setup dev user and document in SQLite
        user = User(
            id=_DEV_USER_ID,
            email="devuser@example.com",
            hashed_password="hashed_secret",
            name="Dev User",
        )
        doc = Document(
            id=uuid.uuid4(),
            user_id=_DEV_USER_ID,
            filename="physics_syllabus.pdf",
            storage_path="/uploads/physics_syllabus.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        db_session.add_all([user, doc])
        db_session.commit()

        mock_json_response = {
            "subject": "Physics",
            "units": [
                {
                    "name": "Mechanics",
                    "topics": [
                        {
                            "name": "Kinematics",
                            "subtopics": ["Vectors", "Motion in 1D"],
                            "mastery": None,
                        }
                    ],
                }
            ],
        }

        mock_instance = MagicMock()
        mock_instance.messages.create.return_value = _make_mock_message(
            json.dumps(mock_json_response)
        )
        mock_anthropic_cls.return_value = mock_instance

        # 2. Call POST /documents/{doc.id}/extract
        response = client.post(f"/documents/{doc.id}/extract")

        assert response.status_code == 200
        data = response.json()
        assert data["subject"] == "Physics"
        assert len(data["units"]) == 1
        assert data["units"][0]["name"] == "Mechanics"

        # Verify persisted in database
        db_tree = get_topic_tree(db_session, _DEV_USER_ID, doc.id)
        assert db_tree is not None
        assert db_tree["subject"] == "Physics"

    def test_get_topics_returns_tree_or_404(self, client, db_session):
        """GET /documents/{doc_id}/topics returns tree when present, 404 when missing."""
        user = User(
            id=_DEV_USER_ID,
            email="devuser@example.com",
            hashed_password="hashed_secret",
            name="Dev User",
        )
        doc_with_tree = Document(
            id=uuid.uuid4(),
            user_id=_DEV_USER_ID,
            filename="math.pdf",
            storage_path="/uploads/math.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        doc_without_tree = Document(
            id=uuid.uuid4(),
            user_id=_DEV_USER_ID,
            filename="empty.pdf",
            storage_path="/uploads/empty.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.pending,
        )
        db_session.add_all([user, doc_with_tree, doc_without_tree])
        db_session.commit()

        sample_tree = {
            "subject": "Mathematics",
            "units": [
                {
                    "name": "Calculus",
                    "topics": [
                        {
                            "name": "Derivatives",
                            "subtopics": ["Chain Rule"],
                            "mastery": None,
                        }
                    ],
                }
            ],
        }
        persist_topic_tree(db_session, _DEV_USER_ID, doc_with_tree.id, sample_tree)

        # GET on document with tree -> 200
        resp_ok = client.get(f"/documents/{doc_with_tree.id}/topics")
        assert resp_ok.status_code == 200
        assert resp_ok.json()["subject"] == "Mathematics"

        # GET on document without tree -> 404
        resp_404 = client.get(f"/documents/{doc_without_tree.id}/topics")
        assert resp_404.status_code == 404

    def test_patch_topic_partial_update_preserves_mastery_and_siblings(self, client, db_session):
        """PATCH /documents/{doc_id}/topics/{topic_id} updates name/subtopics, preserves mastery."""
        user = User(
            id=_DEV_USER_ID,
            email="devuser@example.com",
            hashed_password="hashed_secret",
            name="Dev User",
        )
        doc = Document(
            id=uuid.uuid4(),
            user_id=_DEV_USER_ID,
            filename="chemistry.pdf",
            storage_path="/uploads/chemistry.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        db_session.add_all([user, doc])
        db_session.commit()

        sample_tree = {
            "subject": "Chemistry",
            "units": [
                {
                    "name": "Organic Chemistry",
                    "topics": [
                        {
                            "name": "Hydrocarbons",
                            "subtopics": ["Alkanes", "Alkenes"],
                            "mastery": None,
                        },
                        {
                            "name": "Polymers",
                            "subtopics": ["Addition", "Condensation"],
                            "mastery": None,
                        },
                    ],
                }
            ],
        }
        rows = persist_topic_tree(db_session, _DEV_USER_ID, doc.id, sample_tree)
        topic_hydrocarbons = next(r for r in rows if r.name == "Hydrocarbons")

        # Set a non-null mastery on Hydrocarbons topic in DB
        topic_hydrocarbons.mastery = 0.85
        db_session.commit()

        # PATCH Hydrocarbons topic name and subtopics
        patch_payload = {
            "name": "Advanced Hydrocarbons",
            "subtopics": ["Alkanes", "Alkenes", "Alkynes"],
        }
        resp = client.patch(
            f"/documents/{doc.id}/topics/{topic_hydrocarbons.id}",
            json=patch_payload,
        )
        assert resp.status_code == 200

        # Follow-up GET /documents/{doc.id}/topics to verify state
        resp_get = client.get(f"/documents/{doc.id}/topics")
        assert resp_get.status_code == 200
        tree = resp_get.json()

        topics = tree["units"][0]["topics"]
        hydrocarbons_updated = next(t for t in topics if t["name"] == "Advanced Hydrocarbons")
        polymers = next(t for t in topics if t["name"] == "Polymers")

        # Assert name and subtopics changed
        assert hydrocarbons_updated["subtopics"] == ["Alkanes", "Alkenes", "Alkynes"]

        # Assert mastery was preserved!
        assert hydrocarbons_updated["mastery"] == 0.85

        # Assert sibling topic 'Polymers' was untouched
        assert polymers["subtopics"] == ["Addition", "Condensation"]
        assert polymers["mastery"] is None

    def test_unauthorized_user_document_access_returns_404(self, client, db_session):
        """Requesting another user's document returns 404 and does not leak data."""
        other_user = User(
            id=_OTHER_USER_ID,
            email="otheruser@example.com",
            hashed_password="hashed_secret",
            name="Other User",
        )
        other_doc = Document(
            id=uuid.uuid4(),
            user_id=_OTHER_USER_ID,
            filename="private.pdf",
            storage_path="/uploads/private.pdf",
            mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        db_session.add_all([other_user, other_doc])
        db_session.commit()

        sample_tree = {
            "subject": "Private Subject",
            "units": [
                {
                    "name": "Secret Unit",
                    "topics": [{"name": "Secret Topic", "subtopics": [], "mastery": None}],
                }
            ],
        }
        rows = persist_topic_tree(db_session, _OTHER_USER_ID, other_doc.id, sample_tree)
        secret_topic_id = rows[2].id

        # Current authenticated user is _DEV_USER_ID, attempting to access _OTHER_USER_ID's doc
        assert client.post(f"/documents/{other_doc.id}/extract").status_code == 404
        assert client.get(f"/documents/{other_doc.id}/topics").status_code == 404
        assert client.patch(
            f"/documents/{other_doc.id}/topics/{secret_topic_id}",
            json={"name": "Hacked Name"},
        ).status_code == 404
