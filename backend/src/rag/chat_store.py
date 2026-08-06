"""Chat-turn embedding and retrieval — P5-SRE10.

Separate Qdrant collection from syllabus_chunks (see store.py) since chat
turns are short conversational text, not topic breadcrumbs — keeping them
apart avoids needing a "type" filter on every query.

embed_chat_turn() is meant to be called by whichever endpoint creates a
chat message (P5-SHR7's doubt-answering endpoint, not yet built) — any
ChatMessage row, regardless of session type, can be embedded here so
retrieval can later resurface it as "related past turns."
"""
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy.orm import Session as DBSession

from src.db.models import ChatMessage
from src.rag.embeddings import embed_text
from src.rag.store import get_qdrant_client

CHAT_COLLECTION_NAME = "chat_turns"
VECTOR_SIZE = 768  # nomic-embed-text output dimension


def ensure_chat_collection(client: QdrantClient | None = None) -> None:
    """Create the chat_turns collection if it doesn't already exist."""
    client = client or get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if CHAT_COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=CHAT_COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(size=VECTOR_SIZE, distance=qmodels.Distance.COSINE),
        )


def embed_chat_turn(
    db: DBSession,
    user_id: uuid.UUID | str,
    message_id: uuid.UUID | str,
    client: QdrantClient | None = None,
) -> None:
    """Embed a single ChatMessage row into the chat_turns collection.

    Call this whenever a new chat message is created (from any session
    type — diagnostic, chat, or quiz), so it becomes retrievable later.

    Raises:
        ValueError: if the message doesn't exist or has empty content.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    m_id = uuid.UUID(str(message_id)) if isinstance(message_id, str) else message_id

    message = db.query(ChatMessage).filter(ChatMessage.id == m_id).first()
    if message is None:
        raise ValueError("Chat message not found.")

    if not message.content or not message.content.strip():
        raise ValueError("Cannot embed an empty chat message.")

    client = client or get_qdrant_client()
    ensure_chat_collection(client)

    vector = embed_text(message.content)

    point = qmodels.PointStruct(
        id=str(message.id),
        vector=vector,
        payload={
            "user_id": str(u_id),
            "session_id": str(message.session_id),
            "message_id": str(message.id),
            "role": message.role.value,
            "text": message.content,
            "topic_id": str(message.topic_reference_id) if message.topic_reference_id else None,
            "created_at": message.created_at.isoformat(),
        },
    )
    client.upsert(collection_name=CHAT_COLLECTION_NAME, points=[point])


def search_similar_chat_turns(
    user_id: uuid.UUID | str,
    query_text: str,
    limit: int = 3,
    client: QdrantClient | None = None,
) -> list[dict[str, Any]]:
    """Return the most similar past chat turns for a user's query, across all their sessions."""
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

    client = client or get_qdrant_client()
    ensure_chat_collection(client)

    query_vector = embed_text(query_text)

    results = client.query_points(
        collection_name=CHAT_COLLECTION_NAME,
        query=query_vector,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=str(u_id)))]
        ),
        limit=limit,
    )

    return [
        {
            "message_id": point.payload["message_id"],
            "session_id": point.payload["session_id"],
            "role": point.payload["role"],
            "text": point.payload["text"],
            "score": point.score,
        }
        for point in results.points
    ]