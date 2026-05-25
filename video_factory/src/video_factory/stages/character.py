"""Ensure canonical character sheet exists for face-locked scenes."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_factory.models.schemas import StageName
from video_factory.config import load_project_config as get_config
from video_factory.stages.base import json_artifact, load_state, save_state
from video_factory.utils.files import atomic_write_json
from video_factory.utils.hash import content_hash


def run_character_sheet(project_dir: Path, *, force: bool = False) -> Path:
    """
    Copy or validate character reference into work/json/character_sheet.png.
    Run before images when face lock is enabled.
    """
    config = get_config(project_dir)
    out = project_dir / "work" / "json" / "character_sheet.png"
    meta_path = json_artifact(project_dir, "character_meta.json")

    if out.is_file() and not force:
        return out

    src = None
    if config.character_reference:
        candidate = project_dir / config.character_reference
        if candidate.is_file():
            src = candidate
    if not src:
        fallback = project_dir / "inputs" / "character_reference.png"
        if fallback.is_file():
            src = fallback

    if not src:
        raise FileNotFoundError(
            "Character reference required for face lock. "
            "Add inputs/character_reference.png or set character_reference in config.yaml"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, out)
    atomic_write_json(
        meta_path,
        {
            "source": str(src.relative_to(project_dir)),
            "face_lock": config.enforce_face_lock,
            "message": "Use this exact character in every scene; do not alter face.",
        },
    )

    state = load_state(project_dir)
    state.mark_complete(StageName.CHARACTER, content_hash({"path": str(out)}))
    save_state(project_dir, state)
    return out


def references_ready(project_dir: Path) -> tuple[bool, list[str]]:
    config = get_config(project_dir)
    missing = []
    style = project_dir / (config.style_reference or "inputs/style_reference.png")
    char = project_dir / (config.character_reference or "inputs/character_reference.png")
    if not style.is_file():
        missing.append(str(style.relative_to(project_dir)))
    if not char.is_file():
        missing.append(str(char.relative_to(project_dir)))
    return len(missing) == 0, missing
