"""Per-topic score analysis for a completed quiz (P6-SHI11)."""
import uuid
from collections import OrderedDict

from sqlalchemy.orm import Session as DBSession

from src.db.models import QuizResult, SyllabusTopic
from src.quiz.answer_schemas import QuizScoreAnalysis, TopicScoreBreakdown


DEFAULT_WEAK_THRESHOLD = 0.5


def analyze_quiz_results(
    db: DBSession,
    user_id: uuid.UUID | str,
    quiz_id: uuid.UUID | str,
    weak_threshold: float = DEFAULT_WEAK_THRESHOLD,
) -> QuizScoreAnalysis:
    """Return a user-scoped per-topic score breakdown for one quiz attempt.

    ``QuizResult`` stores one row per question, so grouping those persisted
    scores gives the authoritative analysis for both MCQs and LLM-graded short
    answers. Ungraded questions remain visible but do not skew averages or
    produce a weak-area flag.
    """
    if not 0.0 <= weak_threshold <= 1.0:
        raise ValueError("weak_threshold must be between 0 and 1.")

    normalized_user_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    normalized_quiz_id = uuid.UUID(str(quiz_id)) if isinstance(quiz_id, str) else quiz_id
    rows = (
        db.query(QuizResult, SyllabusTopic.name)
        .join(SyllabusTopic, QuizResult.topic_id == SyllabusTopic.id)
        .filter(QuizResult.user_id == normalized_user_id, QuizResult.quiz_id == normalized_quiz_id)
        .order_by(SyllabusTopic.name.asc())
        .all()
    )
    if not rows:
        raise ValueError("Quiz not found.")

    by_topic: OrderedDict[uuid.UUID, dict] = OrderedDict()
    for result, topic_name in rows:
        bucket = by_topic.setdefault(
            result.topic_id,
            {"topic_name": topic_name, "total": 0, "graded": 0, "score_total": 0.0},
        )
        bucket["total"] += 1
        if result.score is not None:
            bucket["graded"] += 1
            bucket["score_total"] += result.score

    topics = []
    for topic_id, bucket in by_topic.items():
        average_score = (
            bucket["score_total"] / bucket["graded"] if bucket["graded"] else None
        )
        topics.append(
            TopicScoreBreakdown(
                topic_id=topic_id,
                topic_name=bucket["topic_name"],
                questions_total=bucket["total"],
                questions_answered=bucket["graded"],
                average_score=average_score,
                is_weak=average_score is not None and average_score < weak_threshold,
            )
        )

    graded_questions = sum(topic.questions_answered for topic in topics)
    total_score = sum(
        (topic.average_score or 0.0) * topic.questions_answered for topic in topics
    )
    return QuizScoreAnalysis(
        quiz_id=normalized_quiz_id,
        total_questions=len(rows),
        graded_questions=graded_questions,
        average_score=total_score / graded_questions if graded_questions else None,
        weak_threshold=weak_threshold,
        topics=topics,
    )
