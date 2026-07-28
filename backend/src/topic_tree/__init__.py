"""Topic-tree package — P2-SHI4."""

from src.topic_tree.extractor import extract_topic_tree
from src.topic_tree.schemas import Topic, TopicTreeResponse, Unit

__all__ = [
    "extract_topic_tree",
    "TopicTreeResponse",
    "Unit",
    "Topic",
]
