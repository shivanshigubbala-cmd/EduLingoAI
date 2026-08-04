"""Tests for backend/src/rag/ — P5-SRE9 vector store integration."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Document, DocumentStatus, SyllabusTopic, TopicLevel, User
from src.rag.embeddings import embed_text, embed_batch
from src.rag.store import embed_document_topics, _build_topic_chunk_text


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


class TestEmbedText:
    def test_embeds_single_text(self):
        mock_client = MagicMock()
        mock_client.embed.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

        result = embed_text("Kinematics", client=mock_client)

        assert result == [0.1, 0.2, 0.3]
        mock_client.embed.assert_called_once()

    def test_raises_on_empty_text(self):
        with pytest.raises(ValueError, match="empty text"):
            embed_text("", client=MagicMock())

    def test_raises_when_no_vector_returned(self):
        mock_client = MagicMock()
        mock_client.embed.return_value = {"embeddings": []}

        with pytest.raises(ValueError, match="no vector"):
            embed_text("Something", client=mock_client)

    def test_raises_on_client_error(self):
        mock_client = MagicMock()
        mock_client.embed.side_effect = RuntimeError("connection refused")

        with pytest.raises(ValueError, match="Embedding generation failed"):
            embed_text("Something", client=mock_client)


class TestEmbedBatch:
    def test_embeds_multiple_texts(self):
        mock_client = MagicMock()
        mock_client.embed.return_value = {
            "embeddings": [[0.1, 0.2], [0.3, 0.4]]
        }

        result = embed_batch(["Kinematics", "Optics"], client=mock_client)

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]

    def test_empty_list_returns_empty(self):
        assert embed_batch([], client=MagicMock()) == []

    def test_raises_on_mismatched_vector_count(self):
        mock_client = MagicMock()
        mock_client.embed.return_value = {"embeddings": [[0.1, 0.2]]}  # only 1, but 2 texts sent

        with pytest.raises(ValueError, match="unexpected number of vectors"):
            embed_batch(["Kinematics", "Optics"], client=mock_client)


class TestBuildTopicChunkText:
    def test_includes_hierarchical_context(self):
        topic = SyllabusTopic(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            name="Kinematics",
            level=TopicLevel.topic,
        )
        result = _build_topic_chunk_text(topic, ["Physics", "Mechanics"])
        assert result == "Physics > Mechanics > Kinematics"


class TestEmbedDocumentTopics:
    def test_embeds_topic_and_subtopic_nodes_with_context(self, db_session):
        user = User(
            id=uuid.uuid4(), email="student@example.com", hashed_password="x", name="Student"
        )
        doc = Document(
            id=uuid.uuid4(), user_id=user.id, filename="notes.pdf",
            storage_path="/uploads/notes.pdf", mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        subject = SyllabusTopic(
            id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=None,
            name="Physics", level=TopicLevel.subject,
        )
        unit = SyllabusTopic(
            id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=subject.id,
            name="Mechanics", level=TopicLevel.unit,
        )
        topic = SyllabusTopic(
            id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=unit.id,
            name="Kinematics", level=TopicLevel.topic,
        )
        subtopic = SyllabusTopic(
            id=uuid.uuid4(), user_id=user.id, document_id=doc.id, parent_id=topic.id,
            name="Vectors", level=TopicLevel.subtopic,
        )
        db_session.add_all([user, doc, subject, unit, topic, subtopic])
        db_session.commit()

        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value.collections = []

        with patch("src.rag.store.embed_batch") as mock_embed_batch:
            mock_embed_batch.return_value = [[0.1] * 768, [0.2] * 768]

            count = embed_document_topics(db_session, user.id, doc.id, client=mock_qdrant)

        assert count == 2  # topic + subtopic only, not subject/unit
        mock_qdrant.upsert.assert_called_once()

        call_kwargs = mock_qdrant.upsert.call_args.kwargs
        points = call_kwargs["points"]
        assert len(points) == 2
        topic_point = next(p for p in points if p.payload["topic_name"] == "Kinematics")
        assert topic_point.payload["text"] == "Physics > Mechanics > Kinematics"
        assert topic_point.payload["user_id"] == str(user.id)

    def test_raises_when_no_topics_exist(self, db_session):
        user = User(
            id=uuid.uuid4(), email="empty@example.com", hashed_password="x", name="Empty"
        )
        doc = Document(
            id=uuid.uuid4(), user_id=user.id, filename="empty.pdf",
            storage_path="/uploads/empty.pdf", mime_type="application/pdf",
            status=DocumentStatus.parsed,
        )
        db_session.add_all([user, doc])
        db_session.commit()

        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value.collections = []

        with pytest.raises(ValueError, match="No syllabus topics found"):
            embed_document_topics(db_session, user.id, doc.id, client=mock_qdrant)