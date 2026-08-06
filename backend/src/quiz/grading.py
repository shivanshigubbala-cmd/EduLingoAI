"""Auto-grading logic — P6-SHR9.

MCQ answers are graded by exact match (same approach as the diagnostic's
quick right/wrong check, src/diagnostic/adaptive.py). Short answers are
scored via an LLM rubric — a 0-1 score plus a written rationale — since
"correct" isn't a simple string match for free-text responses.

Acceptance criteria (WBS P6-SHR9):
  "MCQs graded exactly; short answers scored via an LLM rubric with a
  written score + rationale."
"""
import json
import re

import ollama

from src.config import get_settings

RUBRIC_SYSTEM_PROMPT = """You are grading a student's short-answer response.

You will be given the question, the expected/reference answer, and the
student's actual answer. Score the student's answer on a scale from 0.0
(completely wrong or blank) to 1.0 (fully correct and complete), allowing
partial credit for partially correct answers.

Respond with ONLY valid JSON, no markdown, no extra text:
{
  "score": <float between 0.0 and 1.0>,
  "rationale": "<one or two sentences explaining the score>"
}
"""


def _clean_json_response(raw_response: str) -> str:
    text = raw_response.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def grade_mcq(correct_answer: str, student_answer: str) -> dict:
    """Exact-match grading for MCQ — no LLM call needed.

    Comparison is case-insensitive and trims whitespace, so "Paris " and
    "paris" both match "Paris", but no partial/fuzzy matching is applied —
    MCQ options are meant to be selected verbatim, not paraphrased.
    """
    is_correct = student_answer.strip().lower() == correct_answer.strip().lower()
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "rationale": "Exact match." if is_correct else f"Expected '{correct_answer}'.",
    }


def grade_short_answer(
    question_text: str,
    correct_answer: str,
    student_answer: str,
    client: "ollama.Client | None" = None,
) -> dict:
    """LLM-rubric grading for short-answer questions.

    Returns a 0-1 score and a written rationale, per the acceptance
    criteria. Falls back to a score of 0.0 with an explanatory rationale
    if the LLM output can't be parsed, rather than raising — a grading
    failure shouldn't crash the whole quiz-submission flow.
    """
    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    user_prompt = (
        f"Question: {question_text}\n"
        f"Reference answer: {correct_answer}\n"
        f"Student's answer: {student_answer}\n"
    )

    messages = [
        {"role": "system", "content": RUBRIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = client.chat(model=settings.LLM_MODEL, messages=messages)
        raw_text = response["message"]["content"]
        cleaned = _clean_json_response(raw_text)
        data = json.loads(cleaned)

        score = float(data["score"])
        score = max(0.0, min(1.0, score))
        rationale = str(data["rationale"])
    except Exception as exc:
        return {
            "is_correct": None,
            "score": 0.0,
            "rationale": f"Grading failed, defaulted to 0: {exc}",
        }

    return {
        "is_correct": score >= 0.5,
        "score": score,
        "rationale": rationale,
    }


def grade_answer(
    question_type: str,
    question_text: str,
    correct_answer: str,
    student_answer: str,
    client: "ollama.Client | None" = None,
) -> dict:
    """Dispatch to the right grading strategy based on question_type.

    Returns {"is_correct": bool | None, "score": float, "rationale": str}.
    is_correct is None for short-answer questions where correctness is a
    matter of degree rather than binary (score is the authoritative signal
    there; is_correct is derived as a >=0.5 convenience flag).
    """
    if question_type == "mcq":
        return grade_mcq(correct_answer, student_answer)
    return grade_short_answer(question_text, correct_answer, student_answer, client=client)