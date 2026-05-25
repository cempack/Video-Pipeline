"""Gemini image generation with Whisk-style reference locking."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

from video_factory.config import AppSettings
from video_factory.models.schemas import VisualPromptDetail
from video_factory.utils.retry import PermanentError, retry_transient
from video_factory.utils.whisk_coherence import WhiskReferences, build_whisk_prompt, postprocess_scene

logger = logging.getLogger("video_factory")


class GeminiWhiskImageProvider:
    """Generate scenes with style + character references (Google Whisk pattern)."""

    def __init__(
        self,
        settings: AppSettings,
        refs: WhiskReferences,
        *,
        visual_style: str = "",
        face_lock_post: bool = True,
    ) -> None:
        if not settings.gemini_api_key:
            raise PermanentError("GEMINI_API_KEY required for whisk_gemini image backend")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_image_model
        self._refs = refs
        self._visual_style = visual_style
        self._face_lock_post = face_lock_post

    def generate(
        self,
        prompt: VisualPromptDetail,
        output_path: Path,
        width: int,
        height: int,
        seed: int | None = None,
    ) -> dict:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        aspect = _aspect_ratio_str(width, height)
        text = build_whisk_prompt(prompt.full_prompt or prompt.subject, self._visual_style)

        def _call() -> bytes:
            parts: list = []
            if self._refs.style_reference and self._refs.style_reference.is_file():
                parts.append("STYLE REFERENCE (copy this art style exactly):")
                parts.append(Image.open(self._refs.style_reference))
            char_path = self._refs.character_sheet or self._refs.character_reference
            if char_path and char_path.is_file():
                parts.append("CHARACTER REFERENCE (same face and design in every scene):")
                parts.append(Image.open(char_path))
            parts.append(text)

            response = self._client.models.generate_content(
                model=self._model,
                contents=parts,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=aspect),
                ),
            )
            for cand in response.candidates or []:
                content = cand.content
                if not content:
                    continue
                for part in content.parts or []:
                    if part.inline_data and part.inline_data.data:
                        return part.inline_data.data
            raise RuntimeError("Gemini returned no image bytes")

        raw = retry_transient(_call)
        img = Image.open(BytesIO(raw))
        img = img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        img.save(output_path, format="PNG")

        postprocess_scene(
            output_path,
            self._refs,
            face_lock=self._face_lock_post,
        )
        return {
            "path": str(output_path),
            "model": self._model,
            "seed": seed,
            "width": width,
            "height": height,
            "backend": "whisk_gemini",
        }


def _aspect_ratio_str(width: int, height: int) -> str:
    if width > height:
        return "16:9"
    if width == height:
        return "1:1"
    return "9:16"
