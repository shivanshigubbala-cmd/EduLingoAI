"""Qdrant vector store integration — P5-SRE9.

Embeds syllabus_topics rows (chunked with hierarchical context) and chat
turns, each tagged with user_id (and topic_id where applicable) as Qdrant
payload so retrieval can be filtered per user and cited back to a topic.
"""
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy.orm import Session as DBSession

from src.config import get_settings
from src.db.models import SyllabusTopic, TopicLevel
from src.rag.embeddings import embed_batch, embed_text

COLLECTION_NAME = "syllabus_chunks"
VECTOR_SIZE = 768  # nomic-embed-text output dimension


def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.VECTOR_STORE_URL)


def ensure_collection(client: QdrantClient | None = None) -> None:
    """Create the collection if it doesn't already exist. Safe to call repeatedly."""
    client = client or get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(size=VECTOR_SIZE, distance=qmodels.Distance.COSINE),
        )


def _build_topic_chunk_text(topic_row: SyllabusTopic, parent_names: list[str]) -> str:
    """Build embeddable text for one topic-tree node with hierarchical context."""
    breadcrumb = " > ".join(parent_names + [topic_row.name])
    return breadcrumb


def embed_document_topics(
    db: DBSession,
    user_id: uuid.UUID | str,
    document_id: uuid.UUID | str,
    client: QdrantClient | None = None,
) -> int:
    """Embed every topic/subtopic node for a document and upsert into Qdrant.

    Returns the number of points written.

    Raises:
        ValueError: if there are no topics to embed for this document.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(document_id)) if isinstance(document_id, str) else document_id

    client = client or get_qdrant_client()
    ensure_collection(client)

    all_rows = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.user_id == u_id, SyllabusTopic.document_id == d_id)
        .all()
    )
    if not all_rows:
        raise ValueError("No syllabus topics found for this document. Run extraction first.")

    rows_by_id = {row.id: row for row in all_rows}

    def _ancestor_names(row: SyllabusTopic) -> list[str]:
        names = []
        current = row.parent_id
        while current is not None and current in rows_by_id:
            parent = rows_by_id[current]
            names.insert(0, parent.name)
            current = parent.parent_id
        return names

    embeddable_rows = [
        row for row in all_rows if row.level in (TopicLevel.topic, TopicLevel.subtopic)
    ]
    if not embeddable_rows:
        raise ValueError("No topic-level nodes to embed for this document.")

    chunk_texts = [
        _build_topic_chunk_text(row, _ancestor_names(row)) for row in embeddable_rows
    ]

    vectors = embed_batch(chunk_texts)

    points = [
        qmodels.PointStruct(
            id=str(row.id),
            vector=vector,
            payload={
                "user_id": str(u_id),
                "document_id": str(d_id),
                "topic_id": str(row.id),
                "topic_name": row.name,
                "level": row.level.value,
                "text": text,
            },
        )
        for row, vector, text in zip(embeddable_rows, vectors, chunk_texts)
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)


def search_similar_chunks(
    user_id: uuid.UUID | str,
    query_text: str,
    limit: int = 5,
    client: QdrantClient | None = None,
) -> list[dict[str, Any]]:
    """Return the most similar syllabus chunks for a user's query, filtered to that user only.

    Raises:
        ValueError: if the query embedding fails.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

    client = client or get_qdrant_client()
    ensure_collection(client)

    query_vector = embed_text(query_text)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=str(u_id)))]
        ),
        limit=limit,
    )

    return [
        {
            "topic_id": point.payload["topic_id"],
            "topic_name": point.payload["topic_name"],
            "text": point.payload["text"],
            "score": point.score,
        }
        for point in results.points
    ]