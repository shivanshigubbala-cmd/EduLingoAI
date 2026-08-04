"""LLM-based quiz generator — P6-SHR8.

Weights the generated quiz toward topics with lower mastery scores, per
docs/architecture.md's Quiz section: "Quiz generator (Claude/LLM) weights
questions toward topics with lower mastery scores."

Follows the same architecture as P3-SRE6's diagnostic generator (Ollama
client, JSON schema validation, retry-on-invalid-JSON) for consistency.
"""
import json
import re
import uuid
from typing import Any

import ollama

from src.config import get_settings
from src.quiz.schemas import QuizQuestionSet

DEFAULT_MAX_QUESTIONS = 10

# A topic that's never been assessed (mastery=None) gets this default weight
# — treated as moderately weak, so it still gets a fair share of questions
# without being assumed either fully mastered or completely unknown.
DEFAULT_MASTERY_FOR_UNSCORED = 0.5

SYSTEM_PROMPT = """You are an expert exam question writer creating a quiz.

You will be given a list of topics, each with a requested number of
questions to write for that specific topic. Generate EXACTLY the requested
number of questions per topic — no more, no fewer.

Use a MIX of question types:
- "mcq": include exactly 4 plausible options in the "options" field, one of
  which is correct.
- "short_answer": a question answerable in one short phrase or sentence;
  "options" MUST be null.

You MUST respond with ONLY valid raw JSON matching this EXACT schema:
{
  "questions": [
    {
      "topic_name": "<must exactly match one of the provided topic names>",
      "question_type": "mcq",
      "question_text": "<question>",
      "options": ["<opt1>", "<opt2>", "<opt3>", "<opt4>"],
      "correct_answer": "<must exactly match one of the options>"
    },
    {
      "topic_name": "<must exactly match one of the provided topic names>",
      "question_type": "short_answer",
      "question_text": "<question>",
      "options": null,
      "correct_answer": "<the expected answer>"
    }
  ]
}

CRITICAL RULES:
1. Output ONLY valid JSON. No markdown code blocks, no intro text, no trailing text.
2. Every "topic_name" MUST exactly match one of the topic names provided.
3. Generate EXACTLY the requested count of questions for each topic.
4. mcq questions MUST have exactly 4 options and a correct_answer matching one option verbatim.
5. short_answer questions MUST have "options": null.
"""


def allocate_question_counts(
    topics: list[dict[str, Any]],
    total_questions: int,
) -> dict[str, int]:
    """Allocate a question count per topic, weighted toward lower mastery.

    Each topic gets weight = 1 - mastery (unscored topics default to
    DEFAULT_MASTERY_FOR_UNSCORED). Counts are allocated proportionally to
    weight using the largest-remainder method, so the total always sums to
    exactly `total_questions` (given at least one topic) while still
    favoring weaker topics with more questions.

    Args:
        topics: list of {"id": ..., "name": ..., "mastery": float | None}.
        total_questions: total number of questions to distribute.

    Returns:
        Dict mapping topic name -> question count (>= 0).
    """
    if not topics or total_questions <= 0:
        return {}

    weights = {
        t["name"]: 1.0 - (t["mastery"] if t["mastery"] is not None else DEFAULT_MASTERY_FOR_UNSCORED)
        for t in topics
    }
    total_weight = sum(weights.values())
    if total_weight <= 0:
        weights = {name: 1.0 for name in weights}
        total_weight = float(len(weights))

    raw_allocations = {
        name: (weight / total_weight) * total_questions for name, weight in weights.items()
    }

    floors = {name: int(raw) for name, raw in raw_allocations.items()}
    remainder = total_questions - sum(floors.values())

    remainders_sorted = sorted(
        raw_allocations.items(), key=lambda item: item[1] - floors[item[0]], reverse=True
    )
    for name, _ in remainders_sorted[:remainder]:
        floors[name] += 1

    return floors


def _clean_json_response(raw_response: str) -> str:
    text = raw_response.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def generate_quiz_questions(
    topics: list[dict[str, Any]],
    max_questions: int = DEFAULT_MAX_QUESTIONS,
    client: "ollama.Client | None" = None,
) -> list[dict[str, Any]]:
    """Generate a quiz weighted toward topics with lower mastery scores.

    Args:
        topics: list of {"id": UUID, "name": str, "mastery": float | None}.
        max_questions: total number of questions to generate.
        client: optional Ollama client for dependency injection (tests).

    Returns:
        List of question dicts (includes correct_answer and the originating
        topic_id — callers strip correct_answer before sending to a client,
        per the same pattern as P3-SRE6).

    Raises:
        ValueError: if topics is empty, or the LLM output can't be parsed
        after one retry.
    """
    if not topics:
        raise ValueError("Cannot generate a quiz: no topics provided.")

    counts_by_name = allocate_question_counts(topics, max_questions)
    topic_id_by_name = {t["name"]: t["id"] for t in topics}

    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    model_name = settings.LLM_MODEL
    user_prompt = "Generate quiz questions for these topics:\n" + "\n".join(
        f"- {name}: {count} question(s)" for name, count in counts_by_name.items() if count > 0
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat(model=model_name, messages=messages)
    raw_text = response["message"]["content"]
    cleaned_text = _clean_json_response(raw_text)

    try:
        data = json.loads(cleaned_text)
        question_set = QuizQuestionSet.model_validate(data)
    except Exception as first_err:
        corrective_prompt = (
            f"Your previous response was invalid JSON or failed schema validation.\n"
            f"Error: {str(first_err)}\n"
            f"Please return ONLY valid JSON matching the exact schema required."
        )
        messages.append({"role": "assistant", "content": raw_text})
        messages.append({"role": "user", "content": corrective_prompt})

        retry_response = client.chat(model=model_name, messages=messages)
        retry_raw_text = retry_response["message"]["content"]
        retry_cleaned = _clean_json_response(retry_raw_text)

        try:
            data = json.loads(retry_cleaned)
            question_set = QuizQuestionSet.model_validate(data)
        except Exception as retry_err:
            raise ValueError(
                f"Failed to generate quiz questions after retry. Final error: {retry_err}"
            ) from retry_err

    results = []
    for q in question_set.questions:
        item = q.model_dump()
        item["topic_id"] = topic_id_by_name.get(q.topic_name)
        item["id"] = uuid.uuid4()
        results.append(item)

    return results