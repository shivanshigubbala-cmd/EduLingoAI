"""LLM-based topic-tree extractor from parsed text — P2-SHI4."""

import json
import re
from typing import Any

import ollama

from src.config import get_settings
from src.topic_tree.schemas import TopicTreeResponse

SYSTEM_PROMPT = """You are an expert educational content analyzer.
Your task is to analyze notes/syllabus text and extract a structured topic tree.

You MUST respond with ONLY valid raw JSON matching this EXACT schema:
{
  "subject": "<Subject Name>",
  "units": [
    {
      "name": "<Unit Name>",
      "topics": [
        {
          "name": "<Topic Name>",
          "subtopics": ["<Subtopic 1>", "<Subtopic 2>"],
          "mastery": null
        }
      ]
    }
  ]
}

CRITICAL RULES:
1. Output ONLY valid JSON. No markdown code blocks (do NOT use ```json), no intro text, no trailing text.
2. subtopics must be a flat array of strings. Do NOT create nested subtopic objects.
3. Every topic MUST have a "mastery" key set explicitly to null. Do NOT set a numerical score or omit it.
4. Do NOT add extra top-level keys outside of "subject" and "units".
"""


def _clean_json_response(raw_response: str) -> str:
    """Remove markdown fences if present and strip leading/trailing whitespace."""
    text = raw_response.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def extract_topic_tree(
    parsed_text: str,
    client: ollama.Client | None = None,
) -> dict[str, Any]:
    """Extract subject, units, topics, and subtopics from parsed text using LLM.

    Args:
        parsed_text: Plain text extracted from syllabus/notes.
        client: Optional Ollama client instance for dependency injection.

    Returns:
        A dictionary matching the TopicTreeResponse schema with mastery forced to None.

    Raises:
        ValueError: If LLM output cannot be parsed or validated after retry.
    """
    settings = get_settings()
    if client is None:
        client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://localhost:11434"))

    model_name = settings.LLM_MODEL  # e.g. "llama3.2:1b" — see note below on config
    user_prompt = f"Extract the topic tree from the following parsed text:\n\n{parsed_text}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Initial LLM call
    response = client.chat(model=model_name, messages=messages)
    raw_text = response["message"]["content"]
    cleaned_text = _clean_json_response(raw_text)

    try:
        data = json.loads(cleaned_text)
        tree = TopicTreeResponse.model_validate(data)
    except Exception as first_err:
        # Retry once with corrective prompt echoing the validation/parsing error
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
            tree = TopicTreeResponse.model_validate(data)
        except Exception as retry_err:
            raise ValueError(
                f"Failed to extract topic tree after retry. Final error: {retry_err}"
            ) from retry_err

    # Explicit safety net: force mastery to None post-parse even if LLM hallucinates a value
    for unit in tree.units:
        for topic in unit.topics:
            topic.mastery = None

    return tree.model_dump()