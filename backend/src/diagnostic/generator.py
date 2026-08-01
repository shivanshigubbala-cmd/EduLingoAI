"""LLM-based diagnostic question generator — P3-SRE6."""
import json
import re
from typing import Any

import ollama

from src.config import get_settings
from src.diagnostic.schemas import DiagnosticQuestionSet

DEFAULT_MAX_QUESTIONS = 8

SYSTEM_PROMPT = """You are an expert exam question writer creating a diagnostic quiz.

You will be given a list of topic names from a student's syllabus. Generate a
capped set of diagnostic questions that spans as many DIFFERENT topics as
possible (do not cluster multiple questions on the same topic unless there
are fewer topics than the requested question count).

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
2. Every "topic_name" MUST exactly match one of the topic names provided in the user message.
3. mcq questions MUST have exactly 4 options and a correct_answer that matches one option verbatim.
4. short_answer questions MUST have "options": null.
5. Generate at most the requested number of questions, spread across distinct topics.
"""


def _clean_json_response(raw_response: str) -> str:
    text = raw_response.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def generate_diagnostic_questions(
    topic_names: list[str],
    max_questions: int = DEFAULT_MAX_QUESTIONS,
    client: "ollama.Client | None" = None,
) -> list[dict[str, Any]]:
    """Generate a capped, topic-spanning set of diagnostic questions.

    Args:
        topic_names: names of leaf-level ("topic") nodes from the syllabus tree.
        max_questions: cap on how many questions to generate (default 8).
        client: optional Ollama client for dependency injection (tests).

    Returns:
        List of dicts matching DiagnosticQuestion shape (includes correct_answer —
        callers are responsible for stripping it before sending to a client).

    Raises:
        ValueError: if the LLM output can't be parsed/validated after one retry.
    """
    if not topic_names:
        raise ValueError("Cannot generate diagnostic questions: no topics provided.")

    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    model_name = settings.LLM_MODEL
    user_prompt = (
        f"Generate at most {max_questions} diagnostic questions spanning these topics:\n"
        + "\n".join(f"- {name}" for name in topic_names)
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
        question_set = DiagnosticQuestionSet.model_validate(data)
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
            question_set = DiagnosticQuestionSet.model_validate(data)
        except Exception as retry_err:
            raise ValueError(
                f"Failed to generate diagnostic questions after retry. Final error: {retry_err}"
            ) from retry_err

    questions = question_set.questions[:max_questions]
    return [q.model_dump() for q in questions]