"""Pluggable image generation backends."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont

from video_factory.config import AppSettings
from video_factory.models.schemas import VisualPromptDetail

logger = logging.getLogger("video_factory")


class ImageProvider(Protocol):
    def generate(
        self,
        prompt: VisualPromptDetail,
        output_path: Path,
        width: int,
        height: int,
        seed: int | None = None,
    ) -> dict: ...


def _apply_style_reference(canvas: Image.Image, style_ref: Path | None) -> Image.Image:
    """Blend a small style-reference strip (mimics Whisk-style consistency checks)."""
    if not style_ref or not style_ref.is_file():
        return canvas
    ref = Image.open(style_ref).convert("RGB")
    ref.thumbnail((canvas.width // 4, canvas.height // 4))
    canvas.paste(ref, (canvas.width - ref.width - 20, 20))
    return canvas


class PlaceholderImageProvider:
    """Deterministic placeholder images for local dev without a diffusion API."""

    def __init__(self, style_reference: Path | None = None) -> None:
        self._style_reference = style_reference

    def generate(
        self,
        prompt: VisualPromptDetail,
        output_path: Path,
        width: int,
        height: int,
        seed: int | None = None,
    ) -> dict:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (width, height), color=(32, 36, 48))
        draw = ImageDraw.Draw(img)
        label = prompt.scene_id
        text = (prompt.full_prompt or prompt.subject or label)[:80]
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.rectangle([40, 40, width - 40, height - 40], outline=(120, 140, 180), width=3)
        draw.text((60, height // 2 - 20), label, fill=(220, 220, 230), font=font)
        draw.text((60, height // 2 + 10), text, fill=(180, 190, 210), font=font)
        img = _apply_style_reference(img, self._style_reference)
        img.save(output_path, format="PNG")
        logger.info("Placeholder image %s", output_path)
        return {
            "path": str(output_path),
            "model": "placeholder",
            "seed": seed,
            "width": width,
            "height": height,
        }


class LocalSDImageProvider(ABC):
    """Hook for local Stable Diffusion; subclass and wire IMAGE_BACKEND=local_sd."""

    @abstractmethod
    def generate(
        self,
        prompt: VisualPromptDetail,
        output_path: Path,
        width: int,
        height: int,
        seed: int | None = None,
    ) -> dict: ...


def get_image_provider(
    settings: AppSettings,
    *,
    style_reference: Path | None = None,
) -> ImageProvider:
    if settings.image_backend == "local_sd":
        raise NotImplementedError(
            "IMAGE_BACKEND=local_sd requires a custom LocalSDImageProvider implementation"
        )
    return PlaceholderImageProvider(style_reference=style_reference)
