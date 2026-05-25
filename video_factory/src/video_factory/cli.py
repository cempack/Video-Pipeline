"""Typer CLI for video-factory pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from PIL import Image, ImageDraw

from video_factory.config import (
    default_project_config,
    ensure_project_layout,
    load_project_config,
    save_project_config,
)
from video_factory.logging import setup_logging
from video_factory.models.schemas import ApprovalStatus, StageName
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
from video_factory.stages.base import json_artifact, load_state, save_state
from video_factory.stages.character import references_ready, run_character_sheet
from video_factory.stages.images import select_image_variant
from video_factory.ui.console import get_console
from video_factory.utils.approval import load_approval, set_approval
from video_factory.utils.asset_library import default_library_dir, register_asset
from video_factory.utils.files import read_json
from video_factory.utils.hash import content_hash

app = typer.Typer(
    name="video-factory",
    help="Local/server Python short-video pipeline with Whisk-style visual coherence.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
run_app = typer.Typer(help="Run a pipeline stage", rich_markup_mode="rich")
app.add_typer(run_app, name="run")

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

STAGE_LABELS: dict[StageName, str] = {
    StageName.RESEARCH: "Research intake",
    StageName.SCRIPT: "Script writer",
    StageName.SCENES: "Scene beats (~3s stills)",
    StageName.PROMPTS: "Visual prompts + style bible",
    StageName.CHARACTER: "Character sheet (face lock)",
    StageName.IMAGES: "Whisk-style images",
    StageName.NARRATION: "Voiceover + silence trim",
    StageName.SUBTITLES: "Subtitles",
    StageName.TIMELINE: "Render manifest",
    StageName.RENDER: "FFmpeg render",
    StageName.QA: "Quality checks",
}


@app.callback()
def main_callback() -> None:
    if not os.environ.get("VF_HEADLESS"):
        get_console().banner()


def _projects_dir(projects: Path | None) -> Path:
    if projects:
        return projects.resolve()
    return Path.cwd() / "projects"


def _resolve_project(projects_dir: Path, project_id: str) -> Path:
    path = projects_dir / project_id
    if not path.is_dir():
        raise typer.BadParameter(f"Project not found: {path}")
    return path


def _write_template_references(project_dir: Path) -> None:
    """Starter style + character PNGs (replace with your Whisk exports)."""
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


@app.command("init-project")
def init_project(
    project_id: str = typer.Argument(..., help="Project folder name"),
    topic: str = typer.Option(..., "--topic", "-t"),
    vertical: str = typer.Option("technology", "--vertical", "-v"),
    duration: int = typer.Option(45, "--duration", "-d"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Create project layout, config, and Whisk reference templates."""
    ui = get_console()
    projects_dir = _projects_dir(projects)
    projects_dir.mkdir(parents=True, exist_ok=True)
    project_dir = projects_dir / project_id
    if project_dir.exists():
        ui.error(f"Project already exists: {project_dir}")
        raise typer.Exit(code=1)

    ensure_project_layout(project_dir)
    config = default_project_config(project_id, topic, vertical=vertical)  # type: ignore[arg-type]
    config.target_duration_sec = duration
    config.style_reference = "inputs/style_reference.png"
    config.character_reference = "inputs/character_reference.png"
    save_project_config(project_dir, config)
    _write_template_references(project_dir)

    (project_dir / "inputs" / "notes.md").write_text(f"# Notes\n\n- Topic: {topic}\n", encoding="utf-8")
    ui.project_header(project_id, topic, vertical)
    ui.success(f"Created {project_dir}")
    ui.info("Edit inputs/style_reference.png and inputs/character_reference.png (Whisk exports)")


@app.command("status")
def status(
    project_id: str = typer.Argument(...),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Pipeline status with approval and reference hints."""
    ui = get_console()
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    config = load_project_config(project_dir)
    state = load_state(project_dir)
    refs_ok, missing = references_ready(project_dir)

    rows: list[tuple[str, str, str]] = []
    for stage in PIPELINE_ORDER:
        rec = state.stages.get(stage.value)
        approval = load_approval(project_dir, stage) if stage == StageName.SCRIPT else None
        if approval and approval.status == ApprovalStatus.PENDING:
            st, detail = "awaiting", "needs approve"
        elif rec and rec.completed_at and not rec.error:
            st, detail = "complete", rec.artifact_hash or ""
        elif rec and rec.error:
            st, detail = "failed", (rec.error or "")[:48]
        else:
            st, detail = "pending", ""
        rows.append((stage.value, st, detail))

    ui.project_header(config.project_id, config.topic, config.vertical)
    ui.status_table(config.project_id, rows, refs_ok=refs_ok)
    if missing:
        ui.warn(f"Missing references: {', '.join(missing)}")


@app.command("approve")
def approve_stage(
    stage: str = typer.Argument(..., help="e.g. script"),
    project_id: str = typer.Argument(...),
    notes: str = typer.Option("", "--notes"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Approve a gated stage after human review."""
    ui = get_console()
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    try:
        stage_enum = StageName(stage)
    except ValueError as exc:
        raise typer.BadParameter(f"Unknown stage: {stage}") from exc

    set_approval(project_dir, stage_enum, ApprovalStatus.APPROVED, notes=notes)
    if stage_enum == StageName.SCRIPT:
        script_path = json_artifact(project_dir, "script_package.json")
        if script_path.exists():
            st = load_state(project_dir)
            st.mark_complete(StageName.SCRIPT, content_hash(read_json(script_path)))
            save_state(project_dir, st)
    ui.success(f"Approved [bold]{stage}[/bold]")


@app.command("select-image")
def select_image(
    project_id: str = typer.Argument(...),
    scene_id: str = typer.Argument(..., help="e.g. s01"),
    variant: str = typer.Option(..., "--variant", "-v", help="e.g. v02"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Pick best image variant; reapplies face lock."""
    ui = get_console()
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    asset = select_image_variant(project_dir, scene_id, variant)
    ui.success(f"{scene_id} → {asset.path} ({variant})")


@app.command("library-add")
def library_add(
    image: Path = typer.Argument(..., exists=True),
    description: str = typer.Option(..., "--desc", "-d"),
    style: str = typer.Option("", "--style"),
    tag: list[str] = typer.Option(None, "--tag"),
) -> None:
    """Register a reusable library asset."""
    ui = get_console()
    entry = register_asset(default_library_dir(), image, description, tags=tag or [], style=style)
    ui.success(f"{entry.asset_id} → {entry.path}")


@app.command("candidates")
def list_candidates(
    project_id: str = typer.Argument(...),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Show image variants per scene."""
    ui = get_console()
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    path = json_artifact(project_dir, "image_candidates.json")
    if not path.exists():
        ui.error("No candidates yet — run: video-factory run images PROJECT")
        raise typer.Exit(code=1)
    ui.candidates_table(read_json(path).get("scenes", []))


def _run_stage(
    project_id: str,
    stage: StageName,
    *,
    force: bool,
    projects: Path | None,
) -> None:
    ui = get_console()
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    config = load_project_config(project_dir)
    setup_logging(project_dir)

    ui.stage_start(stage)
    ui.info(STAGE_LABELS.get(stage, stage.value))

    try:
        runner = STAGE_RUNNERS[stage]
        runner(project_dir, force=force)
    except Exception as exc:
        ui.error(str(exc))
        st = load_state(project_dir)
        st.mark_failed(stage, str(exc))
        save_state(project_dir, st)
        raise typer.Exit(code=1) from exc

    ui.stage_done(stage)


# --- run subcommands ---
def _register_run(name: str, stage: StageName) -> None:
    def _cmd(
        project_id: str = typer.Argument(...),
        force: bool = typer.Option(False, "--force", help="Regenerate even if complete"),
        projects: Optional[Path] = typer.Option(None, "--projects-dir"),
    ) -> None:
        _run_stage(project_id, stage, force=force, projects=projects)

    _cmd.__doc__ = STAGE_LABELS.get(stage, stage.value)
    run_app.command(name, rich_help_panel="Pipeline stages")(_cmd)


for _stage in PIPELINE_ORDER:
    _register_run(_stage.value, _stage)


@run_app.command("all")
def run_all(
    project_id: str = typer.Argument(...),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    force: bool = typer.Option(False, "--force"),
    skip_research: bool = typer.Option(False, "--skip-research"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Run full pipeline with progress and resume support."""
    ui = get_console()
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    config = load_project_config(project_dir)
    setup_logging(project_dir)
    ui.project_header(config.project_id, config.topic, config.vertical)

    stages = [s for s in PIPELINE_ORDER if not (skip_research and s == StageName.RESEARCH)]
    state = load_state(project_dir)

    with ui.progress_task("Pipeline", total=len(stages)) as progress:
        task_id = progress._vf_task_id  # type: ignore[attr-defined]
        for stage in stages:
            if resume and state.is_complete(stage) and not force:
                progress.advance(task_id)
                continue
            try:
                STAGE_RUNNERS[stage](project_dir, force=force)
                state = load_state(project_dir)
            except Exception as exc:
                ui.error(f"{stage.value}: {exc}")
                raise typer.Exit(code=1) from exc
            progress.advance(task_id)

    ui.rule("Done")
    ui.success("Pipeline finished")
    out = project_dir / "outputs" / "final_subtitled.mp4"
    if not out.is_file():
        out = project_dir / "outputs" / "final_clean.mp4"
    if out.is_file():
        ui.info(f"Output: {out}")


if __name__ == "__main__":
    app()
