"""Postgres-backed rolling chat-memory utilities (P5-SHI9)."""

# TODO(P5-SRE9 chat support): once the vector store supports chat
# message embedding/retrieval (not just syllabus_chunks), extend
# summarize_session() to embed compacted/older raw messages via
# embed_batch() and store them so build_chat_context() can optionally
# pull semantically relevant old turns back in via
# search_similar_chunks()-equivalent, instead of relying solely on the
# rolling text summary. Current implementation is Postgres-only.

from src.memory.service import build_chat_context, summarize_session

__all__ = ["build_chat_context", "summarize_session"]
