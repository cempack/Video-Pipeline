"""Layered configuration: env secrets + project YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from video_factory.models.schemas import ProjectConfig, Vertical


class AppSettings(BaseSettings):
    """Global secrets and tool paths from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    elevenlabs_api_key: str = ""
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    image_backend: Literal["placeholder", "local_sd"] = "placeholder"
    gemini_model: str = "gemini-2.0-flash"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_voice_id: str = ""


def load_app_settings() -> AppSettings:
    return AppSettings()


def project_root(projects_dir: Path, project_id: str) -> Path:
    return projects_dir / project_id


def load_project_config(project_dir: Path) -> ProjectConfig:
    config_path = project_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing project config: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return ProjectConfig.model_validate(data)


def save_project_config(project_dir: Path, config: ProjectConfig) -> None:
    config_path = project_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


def ensure_project_layout(project_dir: Path) -> None:
    for sub in ("inputs", "work", "outputs", "logs"):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    (project_dir / "inputs" / "library").mkdir(parents=True, exist_ok=True)
    for sub in (
        "work/images",
        "work/audio",
        "work/subtitles",
        "work/json",
    ):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)


def default_project_config(
    project_id: str,
    topic: str,
    vertical: Vertical = "technology",
) -> ProjectConfig:
    return ProjectConfig(
        project_id=project_id,
        topic=topic,
        vertical=vertical,
        target_duration_sec=45,
        aspect_ratio="9:16",
        language="en",
        voice="default",
        visual_style="editorial illustration",
        subtitle_style="burned_in",
        scene_beat_sec=3.0,
        image_variants_per_scene=4,
        remove_silence=True,
        use_asset_library=True,
    )
