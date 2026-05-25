"""FFmpeg final render."""

from __future__ import annotations

from pathlib import Path

from video_factory.adapters.ffmpeg import FFmpegAdapter
from video_factory.models.schemas import ProjectConfig, RenderTimeline, StageName
from video_factory.stages.base import get_config, get_settings, json_artifact, load_state, outputs_path, require_stage, save_state
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash


def run_render(project_dir: Path, *, force: bool = False) -> Path:
    state = load_state(project_dir)
    clean_out = outputs_path(project_dir, "final_clean.mp4")
    if not force and state.is_complete(StageName.RENDER) and clean_out.exists():
        return clean_out

    require_stage(project_dir, StageName.RENDER, StageName.TIMELINE)
    config = get_config(project_dir)
    timeline = RenderTimeline.model_validate(read_json(json_artifact(project_dir, "timeline.json")))
    ffmpeg = FFmpegAdapter(get_settings())

    subtitled_out = None
    srt_path = project_dir / "work/subtitles/final.srt"
    if config.subtitle_style in ("burned_in", "both"):
        subtitled_out = outputs_path(project_dir, "final_subtitled.mp4")

    result = ffmpeg.render_from_timeline(
        timeline,
        project_dir,
        srt_path=srt_path if srt_path.exists() else None,
        clean_output=clean_out,
        subtitled_output=subtitled_out,
    )

    meta = {
        "clean": str(clean_out.relative_to(project_dir)),
        "subtitled": str(subtitled_out.relative_to(project_dir)) if subtitled_out else None,
        "primary": str(result.relative_to(project_dir)),
    }
    atomic_write_json(outputs_path(project_dir, "render_meta.json"), meta)
    state.mark_complete(StageName.RENDER, content_hash(meta))
    save_state(project_dir, state)
    return result
