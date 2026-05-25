"""Headless pipeline engine (invoked by Go CLI / web UI)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from video_factory.logging import setup_logging
from video_factory.models.schemas import StageName
from video_factory.pipeline import PIPELINE_ORDER, STAGE_RUNNERS, init_project

PIPELINE_ORDER_NAMES = [s.value for s in PIPELINE_ORDER]


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: engine <command> [args]"}))
        sys.exit(1)
    try:
        result = dispatch(sys.argv[1], sys.argv[2:])
        if result is not None:
            print(json.dumps(result, default=str))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


def dispatch(cmd: str, args: list[str]) -> dict[str, Any] | None:
    if cmd == "ping":
        return {"ok": True, "version": "0.1.0"}

    from video_factory.config import load_app_settings

    load_app_settings()
    projects_dir = _parse_projects(args)
    force = "--force" in args

    if cmd == "list_projects":
        projects_dir.mkdir(parents=True, exist_ok=True)
        return {
            "projects": [
                {"id": p.name, "path": str(p)}
                for p in sorted(projects_dir.iterdir())
                if p.is_dir() and (p / "config.yaml").exists()
            ]
        }

    if cmd == "init_project":
        return _init_project(args, projects_dir)
    if cmd == "status":
        return _status(_project_id(args, projects_dir))
    if cmd == "run_stage":
        return _run_stage(args, projects_dir, force)
    if cmd == "approve":
        return _approve(args, projects_dir)
    if cmd == "candidates":
        return _candidates(_project_id(args, projects_dir))
    if cmd == "select_image":
        return _select_image(args, projects_dir)
    if cmd == "library_add":
        return _library_add(args)

    raise ValueError(f"unknown command: {cmd}")


def _parse_projects(args: list[str]) -> Path:
    for i, a in enumerate(args):
        if a == "--projects-dir" and i + 1 < len(args):
            return Path(args[i + 1]).resolve()
    return Path.cwd() / "projects"


def _project_id(args: list[str], projects_dir: Path) -> Path:
    clean = [
        a
        for i, a in enumerate(args)
        if a != "--projects-dir" and not (i > 0 and args[i - 1] == "--projects-dir")
        and a not in ("--force", "--no-resume", "--skip-research")
    ]
    if not clean:
        raise ValueError("project_id required")
    return projects_dir / clean[0]


def _init_project(args: list[str], projects_dir: Path) -> dict:
    project_id = args[0]
    topic, vertical, duration = "Untitled", "technology", 45
    i = 1
    while i < len(args):
        if args[i] == "--topic" and i + 1 < len(args):
            topic = args[i + 1]
            i += 2
        elif args[i] == "--vertical" and i + 1 < len(args):
            vertical = args[i + 1]
            i += 2
        elif args[i] == "--duration" and i + 1 < len(args):
            duration = int(args[i + 1])
            i += 2
        elif args[i] == "--projects-dir":
            i += 2
        else:
            i += 1
    init_project(project_id, topic=topic, vertical=vertical, duration=duration, projects_dir=projects_dir)
    return {"ok": True, "project_id": project_id}


def _status(project_dir: Path) -> dict:
    from video_factory.config import load_project_config
    from video_factory.stages.base import load_state
    from video_factory.stages.character import references_ready
    from video_factory.utils.approval import load_approval

    config = load_project_config(project_dir)
    state = load_state(project_dir)
    refs_ok, missing = references_ready(project_dir)
    stages = []
    for name in PIPELINE_ORDER_NAMES:
        rec = state.stages.get(name)
        st, detail = "pending", ""
        if rec and rec.completed_at and not rec.error:
            st, detail = "complete", rec.artifact_hash or ""
        elif rec and rec.error:
            st, detail = "failed", rec.error or ""
        if name == "script":
            approval = load_approval(project_dir, StageName.SCRIPT)
            if approval and approval.status.value == "pending":
                st = "awaiting"
        stages.append({"name": name, "status": st, "detail": detail})
    return {
        "project_id": config.project_id,
        "topic": config.topic,
        "vertical": config.vertical,
        "refs_ok": refs_ok,
        "missing_refs": missing,
        "stages": stages,
    }


def _run_stage(args: list[str], projects_dir: Path, force: bool) -> dict:
    from video_factory.stages.base import load_state

    stage_name = args[0]
    project_dir = _project_id(args[1:], projects_dir)
    skip_research = "--skip-research" in args
    no_resume = "--no-resume" in args

    setup_logging(project_dir)

    if stage_name == "all":
        ran = []
        for s in PIPELINE_ORDER:
            if s.value == "research" and skip_research:
                continue
            st = load_state(project_dir)
            if not no_resume and st.is_complete(s) and not force:
                continue
            STAGE_RUNNERS[s](project_dir, force=force)
            ran.append(s.value)
        return {"ok": True, "ran": ran}

    stage = StageName(stage_name)
    STAGE_RUNNERS[stage](project_dir, force=force)
    return {"ok": True, "stage": stage_name}


def _approve(args: list[str], projects_dir: Path) -> dict:
    from video_factory.models.schemas import ApprovalStatus
    from video_factory.stages.base import json_artifact, load_state, save_state
    from video_factory.utils.approval import set_approval
    from video_factory.utils.files import read_json
    from video_factory.utils.hash import content_hash

    stage = StageName(args[0])
    project_dir = _project_id(args[1:], projects_dir)
    set_approval(project_dir, stage, ApprovalStatus.APPROVED)
    if stage == StageName.SCRIPT:
        st = load_state(project_dir)
        p = json_artifact(project_dir, "script_package.json")
        if p.exists():
            st.mark_complete(StageName.SCRIPT, content_hash(read_json(p)))
            save_state(project_dir, st)
    return {"ok": True}


def _candidates(project_dir: Path) -> dict:
    from video_factory.stages.base import json_artifact
    from video_factory.utils.files import read_json

    path = json_artifact(project_dir, "image_candidates.json")
    if not path.exists():
        return {"scenes": []}
    return read_json(path)


def _select_image(args: list[str], projects_dir: Path) -> dict:
    from video_factory.stages.images import select_image_variant

    clean = [
        a for i, a in enumerate(args) if not (i > 0 and args[i - 1] == "--projects-dir") and a != "--projects-dir"
    ]
    project_dir = projects_dir / clean[0]
    asset = select_image_variant(project_dir, clean[1], clean[2])
    return {"ok": True, "path": asset.path}


def _library_add(args: list[str]) -> dict:
    from pathlib import Path as P
    from video_factory.utils.asset_library import default_library_dir, register_asset

    image = desc = style = ""
    tags: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--desc" and i + 1 < len(args):
            desc = args[i + 1]
            i += 2
        elif args[i] == "--style" and i + 1 < len(args):
            style = args[i + 1]
            i += 2
        elif args[i] == "--tag" and i + 1 < len(args):
            tags.append(args[i + 1])
            i += 2
        elif not image:
            image = args[i]
            i += 1
        else:
            i += 1
    entry = register_asset(default_library_dir(), P(image), desc, tags=tags, style=style)
    return {"ok": True, "asset_id": entry.asset_id}


if __name__ == "__main__":
    main()
