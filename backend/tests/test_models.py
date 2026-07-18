from src.db import models


def test_all_tables_registered():
    expected = {
        "users", "documents", "syllabus_topics",
        "sessions", "chat_messages", "quiz_results",
    }
    assert expected.issubset(set(models.Base.metadata.tables.keys()))