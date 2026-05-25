"""ElevenLabs text-to-speech adapter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

import httpx

from video_factory.config import AppSettings
from video_factory.utils.retry import PermanentError, retry_transient

logger = logging.getLogger("video_factory")

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class NarrationProvider(Protocol):
    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        context: dict | None = None,
    ) -> dict: ...


class ElevenLabsNarrationProvider:
    def __init__(self, settings: AppSettings) -> None:
        if not settings.elevenlabs_api_key:
            raise PermanentError(
                "ELEVENLABS_API_KEY is required for narration. Set it in .env or environment."
            )
        self._api_key = settings.elevenlabs_api_key
        self._model_id = settings.elevenlabs_model_id
        self._default_voice = settings.elevenlabs_voice_id

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        context: dict | None = None,
    ) -> dict:
        vid = voice_id or self._default_voice
        if not vid:
            raise PermanentError("voice_id required (config voice or ELEVENLABS_VOICE_ID)")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ctx = context or {}

        def _request() -> bytes:
            url = ELEVENLABS_TTS_URL.format(voice_id=vid)
            payload: dict[str, Any] = {
                "text": text,
                "model_id": self._model_id,
            }
            if ctx.get("language_code"):
                payload["language_code"] = ctx["language_code"]
            if ctx.get("previous_text"):
                payload["previous_text"] = ctx["previous_text"]
            if ctx.get("next_text"):
                payload["next_text"] = ctx["next_text"]
            if ctx.get("seed") is not None:
                payload["seed"] = ctx["seed"]
            if ctx.get("voice_settings"):
                payload["voice_settings"] = ctx["voice_settings"]

            headers = {
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            }
            params = {"output_format": ctx.get("output_format", "mp3_44100_128")}
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, json=payload, headers=headers, params=params)
                if resp.status_code >= 400:
                    raise RuntimeError(f"ElevenLabs TTS failed: {resp.status_code} {resp.text[:500]}")
                return resp.content

        audio = retry_transient(_request)
        path.write_bytes(audio)
        logger.info("Wrote narration %s (%d bytes)", path, len(audio))
        return {
            "path": str(path),
            "voice_id": vid,
            "model_id": self._model_id,
            "text_length": len(text),
        }
