"""Pluggable image generation backends."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from video_factory.config import AppSettings
from video_factory.models.schemas import ProjectConfig, VisualPromptDetail
from video_factory.utils.whisk_coherence import WhiskReferences, load_references

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
    config: ProjectConfig,
    project_dir: Path,
) -> ImageProvider:
    refs = load_references(project_dir, config)
    backend = config.image_backend or settings.image_backend

    if backend == "whisk_gemini":
        from video_factory.adapters.image_gemini_whisk import GeminiWhiskImageProvider

        model = config.gemini_image_model or settings.gemini_image_model
        settings_copy = settings.model_copy(update={"gemini_image_model": model})
        return GeminiWhiskImageProvider(
            settings_copy,
            refs,
            visual_style=config.visual_style,
            face_lock_post=config.enforce_face_lock,
        )

    if backend == "whisk_local":
        from video_factory.adapters.image_whisk_local import WhiskLocalImageProvider

        return WhiskLocalImageProvider(refs, visual_style=config.visual_style)

    if backend == "local_sd":
        raise NotImplementedError(
            "IMAGE_BACKEND=local_sd requires a custom LocalSDImageProvider implementation"
        )

    # Legacy placeholder
    from video_factory.adapters.image_whisk_local import WhiskLocalImageProvider

    return WhiskLocalImageProvider(refs, visual_style=config.visual_style)
