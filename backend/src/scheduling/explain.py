"""LLM-based schedule explanation — P4-SRE8.

Generates a short, student-facing chat message explaining why the study
plan is ordered the way it is — specifically referencing actual mastery
scores so the explanation is grounded in real data, not generic filler.
"""
import ollama

from src.config import get_settings
from src.scheduling.schemas import SchedulePlan

SYSTEM_PROMPT = """You are a friendly study coach explaining a generated study
schedule to a student.

You will be given a JSON study plan: a list of days, each with topics that
have a "mastery" score (0.0 to 1.0, where lower means weaker understanding)
and an "estimated_hours" value.

Write a SHORT (3-5 sentences), encouraging chat message that:
1. Explains that topics with lower mastery scores were scheduled earlier.
2. References at least one or two SPECIFIC topic names and their actual
   mastery scores from the plan (do not invent scores or topics).
3. Does not use markdown formatting — plain conversational text only, as
   if speaking directly to the student in a chat window.

Do not repeat the entire schedule day-by-day. Just explain the reasoning
behind the ordering, in a warm and motivating tone.
"""


def generate_schedule_explanation(
    plan: SchedulePlan,
    client: "ollama.Client | None" = None,
) -> str:
    """Generate a short chat-style explanation of why a schedule is ordered as it is.

    Args:
        plan: the persisted SchedulePlan to explain.
        client: optional Ollama client for dependency injection (tests).

    Returns:
        Plain-text explanation message.

    Raises:
        ValueError: if the plan has no topics to explain, or the LLM call fails.
    """
    all_topics = [topic for day in plan.days for topic in day.topics]
    if not all_topics:
        raise ValueError("Cannot explain an empty schedule — no topics found.")

    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    plan_summary = "\n".join(
        f"Day: {day.label}\n"
        + "\n".join(
            f"  - {topic.title} (mastery: {topic.mastery:.2f}, "
            f"{topic.estimated_hours}h)"
            for topic in day.topics
        )
        for day in plan.days
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Here is the study plan:\n\n{plan_summary}"},
    ]

    try:
        response = client.chat(model=settings.LLM_MODEL, messages=messages)
        return response["message"]["content"].strip()
    except Exception as exc:
        raise ValueError(f"Failed to generate schedule explanation: {exc}") from exc