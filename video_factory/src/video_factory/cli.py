"""Typer CLI for video-factory pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from video_factory.config import (
    default_project_config,
    ensure_project_layout,
    load_project_config,
    save_project_config,
)
from video_factory.logging import setup_logging
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
from video_factory.stages.base import load_state

app = typer.Typer(
    name="video-factory",
    help="Local/server Python short-video pipeline",
    no_args_is_help=True,
)
console = Console()

STAGE_RUNNERS = {
    StageName.RESEARCH: run_research,
    StageName.SCRIPT: run_script,
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
    StageName.IMAGES,
    StageName.NARRATION,
    StageName.SUBTITLES,
    StageName.TIMELINE,
    StageName.RENDER,
    StageName.QA,
]


def _projects_dir(projects: Path | None) -> Path:
    if projects:
        return projects.resolve()
    return Path.cwd() / "projects"


def _resolve_project(projects_dir: Path, project_id: str) -> Path:
    path = projects_dir / project_id
    if not path.is_dir():
        raise typer.BadParameter(f"Project not found: {path}")
    return path


@app.command("init-project")
def init_project(
    project_id: str = typer.Argument(..., help="Project folder name"),
    topic: str = typer.Option(..., "--topic", "-t", help="Video topic"),
    vertical: str = typer.Option("technology", "--vertical", "-v"),
    duration: int = typer.Option(45, "--duration", "-d"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Create a new project directory with config and folder layout."""
    projects_dir = _projects_dir(projects)
    projects_dir.mkdir(parents=True, exist_ok=True)
    project_dir = projects_dir / project_id
    if project_dir.exists():
        raise typer.Exit(code=1)
    ensure_project_layout(project_dir)
    config = default_project_config(project_id, topic, vertical=vertical)  # type: ignore[arg-type]
    config.target_duration_sec = duration
    save_project_config(project_dir, config)
    (project_dir / "inputs" / "notes.md").write_text(
        f"# Notes\n\n- Topic: {topic}\n",
        encoding="utf-8",
    )
    console.print(f"[green]Created project[/green] {project_dir}")


run_app = typer.Typer(help="Run a pipeline stage")
app.add_typer(run_app, name="run")


@run_app.command("research")
def run_cmd_research(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.RESEARCH, force=force, projects=projects)


@run_app.command("script")
def run_cmd_script(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.SCRIPT, force=force, projects=projects)


@run_app.command("scenes")
def run_cmd_scenes(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.SCENES, force=force, projects=projects)


@run_app.command("prompts")
def run_cmd_prompts(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.PROMPTS, force=force, projects=projects)


@run_app.command("images")
def run_cmd_images(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.IMAGES, force=force, projects=projects)


@run_app.command("narration")
def run_cmd_narration(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.NARRATION, force=force, projects=projects)


@run_app.command("subtitles")
def run_cmd_subtitles(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.SUBTITLES, force=force, projects=projects)


@run_app.command("render")
def run_cmd_render(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.RENDER, force=force, projects=projects)


@run_app.command("qa")
def run_cmd_qa(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.QA, force=force, projects=projects)


@run_app.command("timeline")
def run_cmd_timeline(
    project_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    _run_stage(project_id, StageName.TIMELINE, force=force, projects=projects)


@run_app.command("all")
def run_all(
    project_id: str = typer.Argument(...),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    force: bool = typer.Option(False, "--force"),
    skip_research: bool = typer.Option(False, "--skip-research"),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Run full pipeline, optionally skipping completed stages."""
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    setup_logging(project_dir)
    state = load_state(project_dir)
    stages = PIPELINE_ORDER
    if skip_research:
        stages = [s for s in stages if s != StageName.RESEARCH]

    for stage in stages:
        if resume and state.is_complete(stage) and not force:
            console.print(f"[dim]Skip {stage.value} (complete)[/dim]")
            continue
        console.print(f"[bold]Running {stage.value}[/bold]")
        runner = STAGE_RUNNERS[stage]
        runner(project_dir, force=force)
        state = load_state(project_dir)

    console.print("[green]Pipeline finished[/green]")


@app.command("status")
def status(
    project_id: str = typer.Argument(...),
    projects: Optional[Path] = typer.Option(None, "--projects-dir"),
) -> None:
    """Show stage completion state for a project."""
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    config = load_project_config(project_dir)
    state = load_state(project_dir)
    table = Table(title=f"Project: {config.project_id}")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Hash/Error")
    for stage in PIPELINE_ORDER:
        rec = state.stages.get(stage.value)
        if rec and rec.completed_at and not rec.error:
            st = "complete"
            detail = rec.artifact_hash or ""
        elif rec and rec.error:
            st = "failed"
            detail = rec.error[:40]
        else:
            st = "pending"
            detail = ""
        table.add_row(stage.value, st, detail)
    console.print(table)


def _run_stage(
    project_id: str,
    stage: StageName,
    *,
    force: bool,
    projects: Path | None,
) -> None:
    projects_dir = _projects_dir(projects)
    project_dir = _resolve_project(projects_dir, project_id)
    setup_logging(project_dir)
    runner = STAGE_RUNNERS[stage]
    result = runner(project_dir, force=force)
    console.print(f"[green]Done {stage.value}[/green]")
    if result is not None:
        console.print(str(result)[:200])


if __name__ == "__main__":
    app()
