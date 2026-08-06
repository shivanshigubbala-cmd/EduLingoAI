"""RAG package — P5-SRE9 (vector store) & P5-SRE10 (retrieval pipeline)."""
from src.rag.chat_store import embed_chat_turn, search_similar_chat_turns
from src.rag.embeddings import embed_batch, embed_text
from src.rag.retrieval import retrieve_context
from src.rag.store import embed_document_topics, search_similar_chunks

__all__ = [
    "embed_text",
    "embed_batch",
    "embed_document_topics",
    "search_similar_chunks",
    "embed_chat_turn",
    "search_similar_chat_turns",
    "retrieve_context",
]