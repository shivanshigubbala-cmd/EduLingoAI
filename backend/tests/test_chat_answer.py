"""Tests for P5-SHR7 — doubt-answering logic.

Mocks the Ollama client, same pattern as other generator/grading tests.
Focuses on the core acceptance criteria: the answer must reference the
specific syllabus topic it draws from.
"""
import uuid
from unittest.mock import MagicMock

from src.rag.chat_answer import answer_doubt, _build_context_block


def _make_mock_message(content_text: str) -> dict:
    return {"message": {"content": content_text}}


class TestBuildContextBlock:
    def test_includes_syllabus_topic_and_text(self):
        retrieval = {
            "syllabus_matches": [
                {"topic_id": str(uuid.uuid4()), "topic_name": "Photosynthesis", "text": "Plants convert light...", "score": 0.9}
            ],
            "chat_matches": [],
        }
        block = _build_context_block(retrieval)
        assert "Photosynthesis" in block
        assert "Plants convert light" in block

    def test_includes_chat_history_when_present(self):
        retrieval = {
            "syllabus_matches": [],
            "chat_matches": [
                {"message_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "role": "user", "text": "What about mitochondria?", "score": 0.8}
            ],
        }
        block = _build_context_block(retrieval)
        assert "mitochondria" in block

    def test_handles_empty_retrieval_gracefully(self):
        block = _build_context_block({"syllabus_matches": [], "chat_matches": []})
        assert "none found" in block.lower()


class TestAnswerDoubt:
    def test_answer_references_top_syllabus_topic(self):
        topic_id = uuid.uuid4()
        retrieval = {
            "syllabus_matches": [
                {"topic_id": str(topic_id), "topic_name": "Newton's Laws", "text": "F=ma...", "score": 0.9}
            ],
            "chat_matches": [],
        }

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            "Based on the topic 'Newton's Laws', force equals mass times acceleration."
        )

        result = answer_doubt("What is Newton's second law?", retrieval, client=mock_client)

        assert result["referenced_topic_id"] == topic_id
        assert result["referenced_topic_name"] == "Newton's Laws"
        assert "Newton's Laws" in result["answer"]

    def test_no_syllabus_match_returns_none_reference(self):
        """If retrieval found nothing relevant, we shouldn't fabricate a topic reference."""
        retrieval = {"syllabus_matches": [], "chat_matches": []}

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message(
            "I don't have syllabus content covering that topic."
        )

        result = answer_doubt("Unrelated question", retrieval, client=mock_client)

        assert result["referenced_topic_id"] is None
        assert result["referenced_topic_name"] is None

    def test_uses_top_match_when_multiple_present(self):
        """Only the highest-ranked syllabus match is cited as the reference,
        even if several were retrieved."""
        top_id = uuid.uuid4()
        retrieval = {
            "syllabus_matches": [
                {"topic_id": str(top_id), "topic_name": "Top Match", "text": "...", "score": 0.95},
                {"topic_id": str(uuid.uuid4()), "topic_name": "Second Match", "text": "...", "score": 0.7},
            ],
            "chat_matches": [],
        }

        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message("Some answer.")

        result = answer_doubt("A question", retrieval, client=mock_client)

        assert result["referenced_topic_id"] == top_id
        assert result["referenced_topic_name"] == "Top Match"

    def test_passes_question_to_llm(self):
        retrieval = {"syllabus_matches": [], "chat_matches": []}
        mock_client = MagicMock()
        mock_client.chat.return_value = _make_mock_message("An answer.")

        answer_doubt("What is gravity?", retrieval, client=mock_client)

        call_kwargs = mock_client.chat.call_args.kwargs
        user_message = call_kwargs["messages"][1]["content"]
        assert "What is gravity?" in user_message