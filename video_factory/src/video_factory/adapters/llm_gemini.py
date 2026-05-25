"""Gemini LLM adapter behind LLMWriter protocol."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from google import genai
from google.genai import types

from video_factory.config import AppSettings
from video_factory.utils.retry import PermanentError, retry_transient
from video_factory.utils.text import extract_json_object

logger = logging.getLogger("video_factory")


class LLMWriter(Protocol):
    def generate_json(self, instruction: str, payload: dict, schema_name: str) -> dict: ...


class GeminiLLMWriter:
    def __init__(self, settings: AppSettings) -> None:
        if not settings.gemini_api_key:
            raise PermanentError(
                "GEMINI_API_KEY is required for LLM stages. Set it in .env or environment."
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def generate_json(self, instruction: str, payload: dict, schema_name: str) -> dict:
        prompt = (
            f"{instruction}\n\n"
            f"Schema: {schema_name}\n"
            f"Input:\n{json.dumps(payload, indent=2)}\n\n"
            "Respond with a single valid JSON object only. No markdown fences."
        )
        return retry_transient(lambda: self._call_with_repair(prompt, schema_name))

    def _call_with_repair(self, prompt: str, schema_name: str) -> dict:
        text = self._generate_text(prompt)
        try:
            return extract_json_object(text)
        except ValueError:
            repair = (
                f"Your previous response was not valid JSON for schema '{schema_name}'.\n"
                f"Broken response:\n{text[:2000]}\n\n"
                "Return ONLY a corrected JSON object."
            )
            repaired = self._generate_text(repair)
            return extract_json_object(repaired)

    def _generate_text(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        text = getattr(response, "text", None) or ""
        if not text and response.candidates:
            parts = response.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") or "" for p in parts)
        if not text:
            raise RuntimeError("Empty response from Gemini")
        logger.debug("Gemini response length=%d", len(text))
        return text
