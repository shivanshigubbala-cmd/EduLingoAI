"""Topic-tree persistence and retrieval module — P2-SHI5."""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import SyllabusTopic, TopicLevel


def persist_topic_tree(
    db: Session,
    user_id: uuid.UUID | str,
    document_id: uuid.UUID | str,
    tree: dict[str, Any],
) -> list[SyllabusTopic]:
    """Flatten an in-memory topic tree dictionary and persist to syllabus_topics table.

    Args:
        db: SQLAlchemy DB Session.
        user_id: Owner user UUID.
        document_id: Originating document UUID.
        tree: Dict matching topic-tree schema (subject, units -> topics -> subtopics).

    Returns:
        List of created SyllabusTopic model instances.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(document_id)) if isinstance(document_id, str) else document_id

    # Clear existing topics for this user and document to prevent duplicates on re-extraction
    db.query(SyllabusTopic).filter(
        SyllabusTopic.user_id == u_id,
        SyllabusTopic.document_id == d_id,
    ).delete(synchronize_session=False)

    rows: list[SyllabusTopic] = []
    base_time = datetime.utcnow()
    offset = 0

    def next_time() -> datetime:
        nonlocal offset
        offset += 1
        return base_time + timedelta(microseconds=offset)

    # 1. Subject (root level)
    subject_node = SyllabusTopic(
        id=uuid.uuid4(),
        user_id=u_id,
        document_id=d_id,
        parent_id=None,
        name=tree.get("subject", "Untitled Subject"),
        level=TopicLevel.subject,
        mastery=None,
        created_at=next_time(),
    )
    rows.append(subject_node)

    # 2. Units
    for unit_dict in tree.get("units", []):
        unit_node = SyllabusTopic(
            id=uuid.uuid4(),
            user_id=u_id,
            document_id=d_id,
            parent_id=subject_node.id,
            name=unit_dict.get("name", "Untitled Unit"),
            level=TopicLevel.unit,
            mastery=None,
            created_at=next_time(),
        )
        rows.append(unit_node)

        # 3. Topics
        for topic_dict in unit_dict.get("topics", []):
            topic_node = SyllabusTopic(
                id=uuid.uuid4(),
                user_id=u_id,
                document_id=d_id,
                parent_id=unit_node.id,
                name=topic_dict.get("name", "Untitled Topic"),
                level=TopicLevel.topic,
                mastery=topic_dict.get("mastery"),
                created_at=next_time(),
            )
            rows.append(topic_node)

            # 4. Subtopics
            for subtopic in topic_dict.get("subtopics", []):
                subtopic_name = (
                    subtopic if isinstance(subtopic, str) else subtopic.get("name", "")
                )
                subtopic_node = SyllabusTopic(
                    id=uuid.uuid4(),
                    user_id=u_id,
                    document_id=d_id,
                    parent_id=topic_node.id,
                    name=subtopic_name,
                    level=TopicLevel.subtopic,
                    mastery=None,
                    created_at=next_time(),
                )
                rows.append(subtopic_node)

    db.add_all(rows)
    db.commit()
    return rows


def get_topic_tree(
    db: Session,
    user_id: uuid.UUID | str,
    document_id: uuid.UUID | str,
) -> dict[str, Any] | None:
    """Query syllabus_topics table by user_id and document_id and reconstruct nested tree dict.

    Args:
        db: SQLAlchemy DB Session.
        user_id: Owner user UUID.
        document_id: Originating document UUID.

    Returns:
        Reconstructed topic tree dictionary matching TopicTreeResponse schema shape,
        or None if no topics exist for the given user_id and document_id.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(document_id)) if isinstance(document_id, str) else document_id

    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.user_id == u_id, SyllabusTopic.document_id == d_id)
        .order_by(SyllabusTopic.created_at.asc())
        .all()
    )
    if not topics:
        return None

    children_by_parent: dict[uuid.UUID | None, list[SyllabusTopic]] = defaultdict(list)
    for topic in topics:
        children_by_parent[topic.parent_id].append(topic)

    subject_nodes = children_by_parent.get(None, [])
    if not subject_nodes:
        subject_nodes = [t for t in topics if t.level == TopicLevel.subject]
        if not subject_nodes:
            return None

    subject_node = subject_nodes[0]

    units_list: list[dict[str, Any]] = []
    unit_nodes = children_by_parent.get(subject_node.id, [])
    for unit_node in unit_nodes:
        topics_list: list[dict[str, Any]] = []
        topic_nodes = children_by_parent.get(unit_node.id, [])
        for topic_node in topic_nodes:
            subtopic_nodes = children_by_parent.get(topic_node.id, [])
            subtopics_list = [st.name for st in subtopic_nodes]
            topics_list.append({
                "name": topic_node.name,
                "subtopics": subtopics_list,
                "mastery": topic_node.mastery,
            })
        units_list.append({
            "name": unit_node.name,
            "topics": topics_list,
        })

    return {
        "subject": subject_node.name,
        "units": units_list,
    }
