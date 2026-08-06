"""Doubt-answering chat — P5-SHR7.

Given a student's doubt (a natural-language question), retrieves the
relevant syllabus topic(s) and related past chat turns (P5-SRE10), and
generates a grounded answer that cites the specific topic/unit it draws
from — not generic LLM knowledge.

Acceptance criteria (WBS P5-SHR7):
  "Answer references the specific syllabus topic/unit it draws from —
  not generic LLM knowledge."
"""
import uuid

import ollama

from src.config import get_settings

SYSTEM_PROMPT = """You are a study assistant answering a student's question
using ONLY the syllabus context provided below. Do not use general
knowledge beyond what's given — if the context doesn't cover the question,
say so honestly rather than guessing.

When you answer, explicitly name the syllabus topic your answer is based
on (e.g. "Based on the topic 'Newton's Laws of Motion'...").

If there is relevant conversation history below, use it for continuity,
but the syllabus context is your primary source of truth.
"""


def _build_context_block(retrieval: dict) -> str:
    """Format retrieved syllabus + chat context into a readable prompt block."""
    lines = []

    syllabus_matches = retrieval.get("syllabus_matches", [])
    if syllabus_matches:
        lines.append("SYLLABUS CONTEXT:")
        for match in syllabus_matches:
            lines.append(f"- Topic: {match['topic_name']}\n  Content: {match['text']}")
    else:
        lines.append("SYLLABUS CONTEXT: (none found for this query)")

    chat_matches = retrieval.get("chat_matches", [])
    if chat_matches:
        lines.append("\nRELATED PAST CONVERSATION:")
        for match in chat_matches:
            lines.append(f"- [{match['role']}]: {match['text']}")

    return "\n".join(lines)


def answer_doubt(
    question: str,
    retrieval: dict,
    client: "ollama.Client | None" = None,
) -> dict:
    """Generate a grounded answer to a student's doubt.

    Args:
        question: the student's natural-language question.
        retrieval: output of src.rag.retrieval.retrieve_context() —
            {"syllabus_matches": [...], "chat_matches": [...]}.
        client: optional Ollama client for dependency injection (tests).

    Returns:
        {
            "answer": "...",
            "referenced_topic_id": UUID | None,  # top syllabus match, if any
            "referenced_topic_name": str | None,
        }
    """
    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    context_block = _build_context_block(retrieval)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context_block}\n\nSTUDENT'S QUESTION:\n{question}"},
    ]

    response = client.chat(model=settings.LLM_MODEL, messages=messages)
    answer_text = response["message"]["content"]

    syllabus_matches = retrieval.get("syllabus_matches", [])
    top_match = syllabus_matches[0] if syllabus_matches else None

    return {
        "answer": answer_text,
        "referenced_topic_id": (
            uuid.UUID(top_match["topic_id"]) if top_match else None
        ),
        "referenced_topic_name": top_match["topic_name"] if top_match else None,
    }