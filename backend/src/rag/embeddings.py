"""Embedding generation via Ollama — P5-SRE9.

Uses nomic-embed-text (local, no API key) rather than OpenAI, consistent
with the team's LLM provider switch (see docs/architecture.md).
"""
import ollama

from src.config import get_settings

EMBEDDING_MODEL = "nomic-embed-text"


def embed_text(text: str, client: "ollama.Client | None" = None) -> list[float]:
    """Generate an embedding vector for a single piece of text.

    Raises:
        ValueError: if the embedding call fails or returns no vector.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    try:
        response = client.embed(model=EMBEDDING_MODEL, input=text)
    except Exception as exc:
        raise ValueError(f"Embedding generation failed: {exc}") from exc

    embeddings = response.get("embeddings")
    if not embeddings or not embeddings[0]:
        raise ValueError("Embedding call returned no vector.")

    return embeddings[0]


def embed_batch(texts: list[str], client: "ollama.Client | None" = None) -> list[list[float]]:
    """Generate embeddings for multiple texts in one Ollama call."""
    if not texts:
        return []

    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    try:
        response = client.embed(model=EMBEDDING_MODEL, input=texts)
    except Exception as exc:
        raise ValueError(f"Batch embedding generation failed: {exc}") from exc

    embeddings = response.get("embeddings")
    if not embeddings or len(embeddings) != len(texts):
        raise ValueError("Embedding call returned an unexpected number of vectors.")

    return embeddings