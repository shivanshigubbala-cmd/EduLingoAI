"""Rolling, Postgres-backed chat-memory compression.

Raw ``chat_messages`` are never changed or deleted.  A chat session's
``summary`` column contains JSON with a summary and the id of the last raw
message represented by it; messages after that id remain the live tail.
"""
import json
from typing import Any

import ollama
from sqlalchemy.orm import Session as DBSession

from src.config import get_settings
from src.db.models import ChatMessage, Session as SessionModel, SessionType


SUMMARY_SYSTEM_PROMPT = """You maintain a concise rolling summary of a student's
chat with a study assistant. Preserve the student's questions, factual answers,
decisions, unresolved questions, and referenced topics. Do not invent facts.
Return only the updated compact summary, with no heading or commentary."""


def _token_count(text: str) -> int:
    """Use a deterministic word-based token estimate until a tokenizer is configured."""
    return len(text.split())


def _parse_summary(value: str | None) -> dict[str, str | None]:
    if not value:
        return {"summary": "", "summarized_through_message_id": None}
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        # Only chat sessions use this convention. Treat legacy plain text as a
        # pre-existing summary rather than silently discarding it.
        return {"summary": value, "summarized_through_message_id": None}
    if not isinstance(data, dict):
        return {"summary": "", "summarized_through_message_id": None}
    summary = data.get("summary", "")
    cursor = data.get("summarized_through_message_id")
    return {
        "summary": summary if isinstance(summary, str) else "",
        "summarized_through_message_id": cursor if isinstance(cursor, str) else None,
    }


def _ordered_messages(db: DBSession, session_id: Any) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )


def _messages_after_cursor(messages: list[ChatMessage], cursor: str | None) -> list[ChatMessage]:
    if cursor is None:
        return messages
    for index, message in enumerate(messages):
        if str(message.id) == cursor:
            return messages[index + 1 :]
    # A stale cursor must not cause prior history to be silently omitted.
    return messages


def _render_messages(messages: list[ChatMessage]) -> str:
    return "\n".join(f"{message.role.value}: {message.content}" for message in messages)


def _get_chat_session(db: DBSession, session_id: Any) -> SessionModel:
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session is None:
        raise ValueError("Chat session not found.")
    if session.type != SessionType.chat:
        raise ValueError("Memory summarization is only supported for chat sessions.")
    return session


def summarize_session(
    db: DBSession,
    session_id: Any,
    token_budget: int,
    turns_threshold: int,
    *,
    client: "ollama.Client | None" = None,
) -> None:
    """Summarize old unsummarized chat turns and advance the rolling cursor.

    When the live tail exceeds ``turns_threshold``, all but its newest
    ``turns_threshold`` messages are compressed. Raw messages are retained in
    Postgres; only their inclusion in future live context changes.
    """
    if token_budget <= 0:
        raise ValueError("token_budget must be positive.")
    if turns_threshold <= 0:
        raise ValueError("turns_threshold must be positive.")

    session = _get_chat_session(db, session_id)
    memory = _parse_summary(session.summary)
    messages = _ordered_messages(db, session.id)
    unsummarized = _messages_after_cursor(messages, memory["summarized_through_message_id"])
    if len(unsummarized) <= turns_threshold:
        return

    chunk = unsummarized[:-turns_threshold]
    prior_summary = memory["summary"] or "(No prior summary.)"
    prompt = (
        f"Existing rolling summary:\n{prior_summary}\n\n"
        "Newly compacted chat turns:\n"
        f"{_render_messages(chunk)}\n\n"
        f"Keep the result under approximately {token_budget} words."
    )
    if client is None:
        settings = get_settings()
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))
    try:
        response = client.chat(
            model=get_settings().LLM_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        summary_text = response["message"]["content"].strip()
    except Exception as exc:
        raise ValueError(f"Failed to summarize chat session: {exc}") from exc
    if not summary_text:
        raise ValueError("Failed to summarize chat session: model returned empty summary.")

    session.summary = json.dumps(
        {
            "summary": summary_text,
            "summarized_through_message_id": str(chunk[-1].id),
        }
    )
    db.commit()


def build_chat_context(
    db: DBSession, session_id: Any, token_budget: int
) -> list[dict[str, str]]:
    """Build bounded LLM messages from the rolling summary and live raw tail.

    The summary is represented as a system message. Newer raw messages are
    retained in chronological order, dropping the oldest live-tail messages if
    needed to fit the requested approximate token budget.
    """
    if token_budget <= 0:
        raise ValueError("token_budget must be positive.")

    session = _get_chat_session(db, session_id)
    memory = _parse_summary(session.summary)
    tail = _messages_after_cursor(
        _ordered_messages(db, session.id), memory["summarized_through_message_id"]
    )
    context: list[dict[str, str]] = []
    used_tokens = 0
    summary_text = memory["summary"] or ""
    if summary_text:
        # A pathological legacy/model response must not make the context exceed
        # its hard budget; retain its most recent words for bounded context.
        summary_words = summary_text.split()
        summary_text = " ".join(summary_words[-token_budget:])
        context.append({"role": "system", "content": f"Conversation summary: {summary_text}"})
        used_tokens = _token_count(summary_text)

    selected_reversed: list[ChatMessage] = []
    for message in reversed(tail):
        message_tokens = _token_count(message.content)
        if used_tokens + message_tokens > token_budget:
            break
        selected_reversed.append(message)
        used_tokens += message_tokens

    for message in reversed(selected_reversed):
        context.append({"role": message.role.value, "content": message.content})
    return context
