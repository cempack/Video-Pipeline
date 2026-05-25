"""Text and JSON parsing helpers."""

from __future__ import annotations

import json
import re


def extract_json_object(text: str) -> dict:
    """Extract first JSON object from model output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in model response")
    parsed = json.loads(match.group())
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object")
    return parsed


def words_per_minute_estimate(word_count: int, wpm: float = 145.0) -> float:
    return (word_count / wpm) * 60.0


def truncate_sentences(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])
