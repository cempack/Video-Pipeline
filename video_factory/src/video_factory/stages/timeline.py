"""Build render timeline from assets and measured durations."""

from __future__ import annotations

from pathlib import Path

from video_factory.models.schemas import AssetManifest, RenderTimeline, ScenePlan, StageName, TimelineScene
from video_factory.stages.base import aspect_dimensions, get_config, json_artifact, load_state, require_stage, save_state
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash


def run_timeline(project_dir: Path, *, force: bool = False) -> RenderTimeline:
    state = load_state(project_dir)
    out = json_artifact(project_dir, "timeline.json")
    if not force and state.is_complete(StageName.TIMELINE) and out.exists():
        return RenderTimeline.model_validate(read_json(out))

    require_stage(project_dir, StageName.TIMELINE, StageName.SUBTITLES)
    config = get_config(project_dir)
    width, height = aspect_dimensions(config.aspect_ratio)
    scenes = ScenePlan.model_validate(read_json(json_artifact(project_dir, "scene_plan.json")))
    manifest = AssetManifest.model_validate(read_json(json_artifact(project_dir, "asset_manifest.json")))
    durations = read_json(json_artifact(project_dir, "audio_durations.json"))

    image_by_scene = {img.scene_id: img.path for img in manifest.images}
    audio_by_scene = manifest.audio.scene_paths

    timeline_scenes: list[TimelineScene] = []
    t = 0.0
    for scene in scenes.scenes:
        dur = float(durations.get(scene.scene_id, max(scene.end_sec - scene.start_sec, 2.5)))
        timeline_scenes.append(
            TimelineScene(
                scene_id=scene.scene_id,
                image_path=image_by_scene.get(scene.scene_id, f"work/images/{scene.scene_id}.png"),
                audio_path=audio_by_scene.get(scene.scene_id, ""),
                start_sec=t,
                duration_sec=dur,
                transition_out="fade" if scene.transition_hint != "cut" else "cut",
            )
        )
        t += dur

    timeline = RenderTimeline(width=width, height=height, fps=30, scenes=timeline_scenes)
    atomic_write_json(out, timeline.model_dump(mode="json"))
    state.mark_complete(StageName.TIMELINE, content_hash(timeline.model_dump()))
    save_state(project_dir, state)
    return timeline
