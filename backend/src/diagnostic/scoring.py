"""Knowledge-level scoring and mastery persistence module — P3-SHI6."""

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import SyllabusTopic
from src.diagnostic.schemas import DiagnosticAnswer


def score_diagnostic(
    answers: list[dict[str, Any] | DiagnosticAnswer],
) -> dict[uuid.UUID, float]:
    """Map diagnostic Q&A answers to per-topic mastery scores (0.0 - 1.0).

    Uses a weighted difficulty formula:
        For a given topic_id, each question has difficulty d_i in [0, 1] (default 0.5).
        Weight w_i = max(d_i, 0.05) to avoid zero-weight division.
        Earned weight e_i = w_i if is_correct is True else 0.0.
        Mastery score = sum(e_i) / sum(w_i), clamped to [0.0, 1.0].

    Topics with zero answered questions are omitted from the returned dict so their
    mastery remains NULL in the database per docs/schema.md design rules.

    Args:
        answers: List of answered question dicts or DiagnosticAnswer instances.

    Returns:
        Dict mapping topic_id UUID -> computed mastery score (0.0 to 1.0).
    """
    validated_answers: list[DiagnosticAnswer] = []
    for item in answers:
        if isinstance(item, DiagnosticAnswer):
            validated_answers.append(item)
        elif isinstance(item, dict):
            validated_answers.append(DiagnosticAnswer.model_validate(item))

    answers_by_topic: dict[uuid.UUID, list[DiagnosticAnswer]] = defaultdict(list)
    for ans in validated_answers:
        answers_by_topic[ans.topic_id].append(ans)

    scores: dict[uuid.UUID, float] = {}

    for topic_id, topic_answers in answers_by_topic.items():
        if not topic_answers:
            continue

        total_weight = 0.0
        earned_weight = 0.0

        for ans in topic_answers:
            w = max(ans.difficulty, 0.05)
            total_weight += w
            if ans.is_correct:
                earned_weight += w

        raw_score = earned_weight / total_weight if total_weight > 0 else 0.0
        clamped_score = min(1.0, max(0.0, float(raw_score)))
        scores[topic_id] = round(clamped_score, 4)

    return scores


def apply_mastery_scores(
    db: Session,
    user_id: uuid.UUID | str,
    document_id: uuid.UUID | str,
    scores: dict[uuid.UUID | str, float],
) -> int:
    """Update mastery field in syllabus_topics table for topics present in scores dict.

    Topics not included in scores dict remain untouched (left as NULL).

    Args:
        db: SQLAlchemy DB Session.
        user_id: Owner user UUID.
        document_id: Originating document UUID.
        scores: Dict mapping topic_id -> mastery float score (0.0 to 1.0).

    Returns:
        Number of updated SyllabusTopic records.
    """
    if not scores:
        return 0

    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(document_id)) if isinstance(document_id, str) else document_id

    normalized_scores: dict[uuid.UUID, float] = {
        (uuid.UUID(str(k)) if isinstance(k, str) else k): float(v)
        for k, v in scores.items()
    }

    topics_to_update = (
        db.query(SyllabusTopic)
        .filter(
            SyllabusTopic.user_id == u_id,
            SyllabusTopic.document_id == d_id,
            SyllabusTopic.id.in_(list(normalized_scores.keys())),
        )
        .all()
    )

    updated_count = 0
    for topic in topics_to_update:
        if topic.id in normalized_scores:
            topic.mastery = normalized_scores[topic.id]
            updated_count += 1

    db.commit()
    return updated_count
