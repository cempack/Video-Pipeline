"""Shared stage utilities."""

from __future__ import annotations

from pathlib import Path

from video_factory.config import AppSettings, load_project_config
from video_factory.models.schemas import ProjectState, StageName
from video_factory.utils.files import atomic_write_json, outputs_path, read_json
from video_factory.utils.hash import content_hash


def state_path(project_dir: Path) -> Path:
    return project_dir / "state.json"


def load_state(project_dir: Path) -> ProjectState:
    path = state_path(project_dir)
    if not path.exists():
        return ProjectState()
    return ProjectState.model_validate(read_json(path))


def save_state(project_dir: Path, state: ProjectState) -> None:
    atomic_write_json(state_path(project_dir), state.model_dump(mode="json"))


def json_artifact(project_dir: Path, rel: str) -> Path:
    return project_dir / "work" / "json" / rel


def require_stage(project_dir: Path, stage: StageName, prereq: StageName) -> None:
    state = load_state(project_dir)
    if not state.is_complete(prereq):
        raise RuntimeError(f"Stage '{prereq.value}' must complete before '{stage.value}'")


def aspect_dimensions(aspect: str) -> tuple[int, int]:
    if aspect == "16:9":
        return 1920, 1080
    if aspect == "1:1":
        return 1080, 1080
    return 1080, 1920


def get_settings() -> AppSettings:
    from video_factory.config import load_app_settings

    return load_app_settings()


def get_config(project_dir: Path):
    return load_project_config(project_dir)
