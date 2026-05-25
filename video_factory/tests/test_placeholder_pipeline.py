"""Offline pipeline test: placeholder images, no LLM/TTS APIs."""

from pathlib import Path

import pytest

from video_factory.config import ensure_project_layout, save_project_config, default_project_config
from video_factory.models.schemas import (
    AssetManifest,
    ImageAsset,
    ScenePlan,
    SceneSpec,
    ScriptPackage,
    StageName,
)
from video_factory.stages.base import load_state, save_state, json_artifact
from video_factory.stages.images import run_images
from video_factory.stages.prompts import run_prompts
from video_factory.stages.subtitles import run_subtitles
from video_factory.stages.timeline import run_timeline
from video_factory.utils.files import atomic_write_json


@pytest.fixture
def mini_project(tmp_path: Path) -> Path:
    from PIL import Image

    project_dir = tmp_path / "test-proj"
    ensure_project_layout(project_dir)
    cfg = default_project_config("test-proj", "Test topic")
    save_project_config(project_dir, cfg)
    Image.new("RGB", (200, 300), (255, 240, 220)).save(project_dir / "inputs" / "style_reference.png")
    Image.new("RGBA", (200, 300), (255, 200, 150, 255)).save(project_dir / "inputs" / "character_reference.png")

    script = ScriptPackage(
        title="Test",
        hook="Quick hook.",
        full_script="Line one. Line two.",
        word_count=6,
        estimated_duration_sec=4.0,
    )
    atomic_write_json(json_artifact(project_dir, "script_package.json"), script.model_dump(mode="json"))

    scenes = ScenePlan(
        scenes=[
            SceneSpec(
                scene_id="s01",
                narration="Line one.",
                start_sec=0,
                end_sec=2,
                visual_prompt="abstract tech",
                image_prompt="abstract tech illustration",
            ),
            SceneSpec(
                scene_id="s02",
                narration="Line two.",
                start_sec=2,
                end_sec=4,
                visual_prompt="team planning",
                image_prompt="team planning editorial",
            ),
        ]
    )
    atomic_write_json(json_artifact(project_dir, "scene_plan.json"), scenes.model_dump(mode="json"))

    from video_factory.models.schemas import StyleBible, VisualPromptDetail

    style = StyleBible(visual_style="editorial illustration")
    atomic_write_json(json_artifact(project_dir, "style_bible.json"), style.model_dump(mode="json"))
    prompts = [
        VisualPromptDetail(scene_id="s01", full_prompt="tech abstract", subject="chips"),
        VisualPromptDetail(scene_id="s02", full_prompt="team at board", subject="team"),
    ]
    atomic_write_json(
        json_artifact(project_dir, "visual_prompts.json"),
        {"prompts": [p.model_dump() for p in prompts]},
    )

    state = load_state(project_dir)
    for stage in (StageName.SCRIPT, StageName.SCENES, StageName.PROMPTS):
        state.mark_complete(stage)
    save_state(project_dir, state)
    return project_dir


def test_run_images_placeholder(mini_project: Path):
    manifest = run_images(mini_project, force=True)
    assert len(manifest.images) == 2
    for img in manifest.images:
        assert (mini_project / img.path).is_file()


def test_timeline_requires_subtitles_prereq(mini_project: Path):
    # Seed fake audio durations and manifest for timeline without TTS
    atomic_write_json(
        json_artifact(mini_project, "audio_durations.json"),
        {"s01": 2.0, "s02": 2.0},
    )
    atomic_write_json(
        json_artifact(mini_project, "asset_manifest.json"),
        AssetManifest(
            images=[
                ImageAsset(scene_id="s01", prompt="a", path="work/images/s01.png"),
                ImageAsset(scene_id="s02", prompt="b", path="work/images/s02.png"),
            ],
        ).model_dump(mode="json"),
    )
    run_images(mini_project, force=False)
    state = load_state(mini_project)
    state.mark_complete(StageName.NARRATION)
    state.mark_complete(StageName.SUBTITLES)
    save_state(mini_project, state)
    # subtitles stage needs narration complete - write minimal srt via run_subtitles after faking
    from video_factory.stages.subtitles import run_subtitles

    run_subtitles(mini_project, force=True)
    timeline = run_timeline(mini_project, force=True)
    assert len(timeline.scenes) == 2
    assert timeline.width == 1080
