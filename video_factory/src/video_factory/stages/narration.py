"""Per-scene TTS with silence removal and optional loudness humanization."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_factory.adapters.ffmpeg import FFmpegAdapter
from video_factory.adapters.tts_elevenlabs import ElevenLabsNarrationProvider
from video_factory.models.schemas import AssetManifest, ScenePlan, StageName
from video_factory.stages.base import get_config, get_settings, json_artifact, load_state, require_stage, save_state
from video_factory.utils.approval import require_approved
from video_factory.utils.audio import apply_subtle_loudness_variation, remove_silence_ffmpeg
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash


def run_narration(project_dir: Path, *, force: bool = False) -> AssetManifest:
    state = load_state(project_dir)
    manifest_path = json_artifact(project_dir, "asset_manifest.json")
    if not force and state.is_complete(StageName.NARRATION) and manifest_path.exists():
        m = AssetManifest.model_validate(read_json(manifest_path))
        if m.audio.voiceover_path:
            return m

    require_stage(project_dir, StageName.NARRATION, StageName.SCENES)
    config = get_config(project_dir)
    if config.require_script_approval:
        require_approved(project_dir, StageName.SCRIPT)

    scenes = ScenePlan.model_validate(read_json(json_artifact(project_dir, "scene_plan.json")))
    settings = get_settings()
    tts = ElevenLabsNarrationProvider(settings)
    ffmpeg = FFmpegAdapter(settings)

    voice_id = config.voice if config.voice != "default" else settings.elevenlabs_voice_id
    scene_paths: dict[str, str] = {}
    prev_text = ""
    scene_list = scenes.scenes

    for i, scene in enumerate(scene_list):
        raw_rel = f"work/audio/{scene.scene_id}_raw.mp3"
        out_rel = f"work/audio/{scene.scene_id}.mp3"
        raw_path = project_dir / raw_rel
        out_path = project_dir / out_rel
        next_text = scene_list[i + 1].narration if i + 1 < len(scene_list) else ""

        if not out_path.exists() or force:
            tts.synthesize(
                scene.narration,
                voice_id,
                str(raw_path),
                context={
                    "language_code": config.language[:2] if config.language else None,
                    "previous_text": prev_text,
                    "next_text": next_text,
                },
            )
            processed = raw_path
            if config.remove_silence:
                trimmed = project_dir / f"work/audio/{scene.scene_id}_trim.mp3"
                remove_silence_ffmpeg(
                    settings.ffmpeg_bin,
                    raw_path,
                    trimmed,
                    threshold_db=config.silence_threshold_db,
                    min_silence_sec=config.silence_min_duration_sec,
                )
                processed = trimmed
            if config.audio_loudness_variation:
                varied = project_dir / f"work/audio/{scene.scene_id}_var.mp3"
                apply_subtle_loudness_variation(
                    settings.ffmpeg_bin,
                    processed,
                    varied,
                    seed=hash(scene.scene_id) % 10_000,
                )
                processed = varied
            shutil.copy2(processed, out_path)

        scene_paths[scene.scene_id] = out_rel
        prev_text = scene.narration

    voiceover_rel = "work/audio/voiceover.mp3"
    voiceover_path = project_dir / voiceover_rel
    _concat_audio(ffmpeg, [project_dir / p for p in scene_paths.values()], voiceover_path)

    manifest = AssetManifest()
    if manifest_path.exists():
        manifest = AssetManifest.model_validate(read_json(manifest_path))
    manifest.audio = manifest.audio.model_copy(
        update={"voiceover_path": voiceover_rel, "scene_paths": scene_paths}
    )
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))

    durations = {}
    for sid, rel in scene_paths.items():
        durations[sid] = ffmpeg.probe_duration(project_dir / rel)
    atomic_write_json(json_artifact(project_dir, "audio_durations.json"), durations)

    state.mark_complete(StageName.NARRATION, content_hash(manifest.audio.model_dump()))
    save_state(project_dir, state)
    return manifest


def _concat_audio(ffmpeg: FFmpegAdapter, paths: list[Path], output: Path) -> None:
    if len(paths) == 1:
        output.write_bytes(paths[0].read_bytes())
        return
    list_file = output.parent / "audio_concat.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in paths) + "\n", encoding="utf-8")
    ffmpeg.run(
        [
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(output),
        ]
    )
