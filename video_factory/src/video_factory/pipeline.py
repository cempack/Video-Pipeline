"""Pipeline registry and project bootstrap (used by engine only)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from video_factory.config import (
    default_project_config,
    ensure_project_layout,
    save_project_config,
)
from video_factory.models.schemas import StageName
from video_factory.stages import (
    run_images,
    run_narration,
    run_prompts,
    run_qa,
    run_render,
    run_research,
    run_scenes,
    run_script,
    run_subtitles,
    run_timeline,
)
from video_factory.stages.character import run_character_sheet

STAGE_RUNNERS = {
    StageName.RESEARCH: run_research,
    StageName.SCRIPT: run_script,
    StageName.CHARACTER: run_character_sheet,
    StageName.SCENES: run_scenes,
    StageName.PROMPTS: run_prompts,
    StageName.IMAGES: run_images,
    StageName.NARRATION: run_narration,
    StageName.SUBTITLES: run_subtitles,
    StageName.TIMELINE: run_timeline,
    StageName.RENDER: run_render,
    StageName.QA: run_qa,
}

PIPELINE_ORDER: list[StageName] = [
    StageName.RESEARCH,
    StageName.SCRIPT,
    StageName.SCENES,
    StageName.PROMPTS,
    StageName.CHARACTER,
    StageName.IMAGES,
    StageName.NARRATION,
    StageName.SUBTITLES,
    StageName.TIMELINE,
    StageName.RENDER,
    StageName.QA,
]


def write_template_references(project_dir: Path) -> None:
    style_path = project_dir / "inputs" / "style_reference.png"
    char_path = project_dir / "inputs" / "character_reference.png"
    if not style_path.exists():
        img = Image.new("RGB", (540, 960), (235, 245, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([40, 200, 500, 700], outline=(40, 50, 70), width=4)
        draw.text((60, 220), "STYLE REF", fill=(30, 40, 60))
        draw.text((60, 260), "Replace with your Whisk style board", fill=(80, 90, 110))
        img.save(style_path)
    if not char_path.exists():
        img = Image.new("RGBA", (400, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([120, 80, 280, 240], fill=(255, 220, 180, 255))
        draw.rectangle([100, 240, 300, 520], fill=(60, 120, 200, 255))
        draw.text((110, 540), "CHARACTER", fill=(30, 40, 60))
        img.save(char_path)


def init_project(
    project_id: str,
    *,
    topic: str,
    vertical: str = "technology",
    duration: int = 45,
    projects_dir: Path,
) -> Path:
    projects_dir.mkdir(parents=True, exist_ok=True)
    project_dir = projects_dir / project_id
    if project_dir.exists():
        raise FileExistsError(f"Project already exists: {project_dir}")

    ensure_project_layout(project_dir)
    config = default_project_config(project_id, topic, vertical=vertical)  # type: ignore[arg-type]
    config.target_duration_sec = duration
    config.style_reference = "inputs/style_reference.png"
    config.character_reference = "inputs/character_reference.png"
    save_project_config(project_dir, config)
    write_template_references(project_dir)
    (project_dir / "inputs" / "notes.md").write_text(
        f"# Notes\n\n- Topic: {topic}\n",
        encoding="utf-8",
    )
    return project_dir
