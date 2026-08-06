"""RAG retrieval pipeline — P5-SRE10.

Given a doubt (a natural-language question), returns the relevant
syllabus topic(s) plus related past chat turns, combined into one
structured context object the eventual doubt-answering endpoint
(P5-SHR7) can pass straight into an LLM prompt.
"""
import uuid
from typing import Any

from src.rag.chat_store import search_similar_chat_turns
from src.rag.store import search_similar_chunks


def retrieve_context(
    user_id: uuid.UUID | str,
    query: str,
    topic_limit: int = 3,
    chat_limit: int = 3,
) -> dict[str, Any]:
    """Retrieve combined context for a student's doubt.

    Returns:
        {
            "syllabus_matches": [...],  # from search_similar_chunks
            "chat_matches": [...],      # from search_similar_chat_turns
        }

    Each sub-search fails independently — if one raises (e.g. empty
    collection), it's caught and returned as an empty list rather than
    failing the whole retrieval, since a doubt can still be partially
    grounded even with no chat history yet.
    """
    try:
        syllabus_matches = search_similar_chunks(user_id, query, limit=topic_limit)
    except ValueError:
        syllabus_matches = []

    try:
        chat_matches = search_similar_chat_turns(user_id, query, limit=chat_limit)
    except ValueError:
        chat_matches = []

    return {
        "syllabus_matches": syllabus_matches,
        "chat_matches": chat_matches,
    }