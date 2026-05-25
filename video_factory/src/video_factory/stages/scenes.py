"""Scene segmentation from script."""

from __future__ import annotations

from pathlib import Path

from video_factory.adapters.llm_gemini import GeminiLLMWriter
from video_factory.models.schemas import ScenePlan, ScriptPackage, StageName
from video_factory.stages.base import get_config, get_settings, json_artifact, load_state, require_stage, save_state
from video_factory.utils.approval import require_approved
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash
from video_factory.utils.prompts_loader import load_project_instructions, merge_instruction


def run_scenes(project_dir: Path, *, force: bool = False) -> ScenePlan:
    state = load_state(project_dir)
    out = json_artifact(project_dir, "scene_plan.json")
    if not force and state.is_complete(StageName.SCENES) and out.exists():
        return ScenePlan.model_validate(read_json(out))

    require_stage(project_dir, StageName.SCENES, StageName.SCRIPT)
    config = get_config(project_dir)
    if config.require_script_approval:
        require_approved(project_dir, StageName.SCRIPT)
    script = ScriptPackage.model_validate(read_json(json_artifact(project_dir, "script_package.json")))

    beat = config.scene_beat_sec
    est_scenes = max(int(config.target_duration_sec / beat), 8)
    instructions = load_project_instructions(project_dir)
    writer = GeminiLLMWriter(get_settings())
    raw = writer.generate_json(
        merge_instruction(
            (
                f"Split the script into ~{est_scenes} visual scenes for a faceless short. "
                f"Target ~{beat}s per still frame (new image every ~3 seconds). "
                "Static illustrations only — no animation. "
                "Return JSON: { scenes: [ { scene_id, narration, start_sec, end_sec, "
                "visual_prompt, on_screen_text, transition_hint, image_prompt } ] }. "
                "One sentence or clause per scene. Simple compositions, consistent character. "
                "IDs like s01, s02."
            ),
            instructions,
            "scenes",
        ),
        {
            "script": script.model_dump(),
            "target_duration_sec": config.target_duration_sec,
            "visual_style": config.visual_style,
        },
        "ScenePlan",
    )
    plan = ScenePlan.model_validate(raw)
    _normalize_scene_timing(plan, config.target_duration_sec, config.scene_beat_sec)

    atomic_write_json(out, plan.model_dump(mode="json"))
    state.mark_complete(StageName.SCENES, content_hash(plan.model_dump()))
    save_state(project_dir, state)
    return plan


def _normalize_scene_timing(plan: ScenePlan, target_sec: float, beat_sec: float) -> None:
    if not plan.scenes:
        return
    total_est = sum(max(s.end_sec - s.start_sec, 0) for s in plan.scenes)
    if total_est <= 0:
        per = target_sec / len(plan.scenes)
        t = 0.0
        for s in plan.scenes:
            s.start_sec = t
            s.end_sec = t + per
            t += per
        return
    scale = target_sec / total_est
    t = 0.0
    for s in plan.scenes:
        dur = max((s.end_sec - s.start_sec) * scale, beat_sec * 0.8)
        s.start_sec = t
        s.end_sec = t + dur
        t += dur
