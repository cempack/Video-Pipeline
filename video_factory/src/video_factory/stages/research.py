"""Research intake: normalize local notes into research_pack.json."""

from __future__ import annotations

from pathlib import Path

from video_factory.models.schemas import ProjectConfig, ResearchPack, ResearchSource, StageName
from video_factory.stages.base import get_config, json_artifact, load_state, save_state
from video_factory.utils.files import atomic_write_json, inputs_path
from video_factory.utils.hash import content_hash


def run_research(project_dir: Path, *, force: bool = False) -> ResearchPack:
    state = load_state(project_dir)
    out = json_artifact(project_dir, "research_pack.json")
    if not force and state.is_complete(StageName.RESEARCH) and out.exists():
        from video_factory.utils.files import read_json

        return ResearchPack.model_validate(read_json(out))

    config = get_config(project_dir)
    pack = _build_research_pack(project_dir, config)
    atomic_write_json(out, pack.model_dump(mode="json"))
    state.mark_complete(StageName.RESEARCH, content_hash(pack.model_dump()))
    save_state(project_dir, state)
    return pack


def _build_research_pack(project_dir: Path, config: ProjectConfig) -> ResearchPack:
    notes_path = inputs_path(project_dir, "notes.md")
    sources_path = inputs_path(project_dir, "sources.txt")
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    sources: list[ResearchSource] = []
    if sources_path.exists():
        for line in sources_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("http"):
                sources.append(ResearchSource(url=line, title=line))
            else:
                sources.append(ResearchSource(title=line, excerpt=line))
    return ResearchPack(
        topic=config.topic,
        summary=notes[:500] if notes else f"Brief for: {config.topic}",
        key_points=[ln.strip("- ") for ln in notes.splitlines() if ln.strip().startswith("-")],
        sources=sources,
        notes=notes,
        grounding_required=config.vertical in ("politics", "economics"),
    )
