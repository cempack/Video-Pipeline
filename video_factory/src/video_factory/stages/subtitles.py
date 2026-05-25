"""Subtitle generation from measured scene timings."""

from __future__ import annotations

from pathlib import Path

from video_factory.models.schemas import (
    AssetManifest,
    ScenePlan,
    StageName,
    SubtitleCue,
    SubtitleSegments,
)
from video_factory.stages.base import json_artifact, load_state, require_stage, save_state
from video_factory.utils.files import work_path
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash


def run_subtitles(project_dir: Path, *, force: bool = False) -> SubtitleSegments:
    state = load_state(project_dir)
    segments_path = work_path(project_dir, "subtitles", "subtitle_segments.json")
    if not force and state.is_complete(StageName.SUBTITLES) and segments_path.exists():
        return SubtitleSegments.model_validate(read_json(segments_path))

    require_stage(project_dir, StageName.SUBTITLES, StageName.NARRATION)
    scenes = ScenePlan.model_validate(read_json(json_artifact(project_dir, "scene_plan.json")))
    durations_path = json_artifact(project_dir, "audio_durations.json")
    durations = read_json(durations_path) if durations_path.exists() else {}

    cues: list[SubtitleCue] = []
    t = 0.0
    idx = 1
    for scene in scenes.scenes:
        dur = float(durations.get(scene.scene_id, max(scene.end_sec - scene.start_sec, 2.0)))
        cues.append(
            SubtitleCue(
                index=idx,
                start_sec=t,
                end_sec=t + dur,
                text=scene.narration.strip(),
            )
        )
        t += dur
        idx += 1

    segments = SubtitleSegments(cues=cues)
    srt_rel = "work/subtitles/final.srt"
    vtt_rel = "work/subtitles/final.vtt"
    _write_srt(project_dir / srt_rel, segments)
    _write_vtt(project_dir / vtt_rel, segments)
    atomic_write_json(segments_path, segments.model_dump(mode="json"))

    manifest_path = json_artifact(project_dir, "asset_manifest.json")
    manifest = AssetManifest.model_validate(read_json(manifest_path))
    manifest.subtitles = manifest.subtitles.model_copy(
        update={
            "srt_path": srt_rel,
            "vtt_path": vtt_rel,
            "segments_path": "work/subtitles/subtitle_segments.json",
        }
    )
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))

    state.mark_complete(StageName.SUBTITLES, content_hash(segments.model_dump()))
    save_state(project_dir, state)
    return segments


def _format_srt_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(path: Path, segments: SubtitleSegments) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for cue in segments.cues:
        lines.append(str(cue.index))
        lines.append(f"{_format_srt_time(cue.start_sec)} --> {_format_srt_time(cue.end_sec)}")
        lines.append(cue.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_vtt(path: Path, segments: SubtitleSegments) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["WEBVTT", ""]
    for cue in segments.cues:
        start = _format_vtt_time(cue.start_sec)
        end = _format_vtt_time(cue.end_sec)
        lines.append(f"{cue.index}")
        lines.append(f"{start} --> {end}")
        lines.append(cue.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_vtt_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
