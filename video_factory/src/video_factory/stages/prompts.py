"""Visual prompt generation and style bible."""

from __future__ import annotations

from pathlib import Path

from video_factory.adapters.llm_gemini import GeminiLLMWriter
from video_factory.models.schemas import ScenePlan, StageName, StyleBible, VisualPromptDetail
from video_factory.stages.base import get_config, get_settings, json_artifact, load_state, require_stage, save_state
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash


def run_prompts(project_dir: Path, *, force: bool = False) -> list[VisualPromptDetail]:
    state = load_state(project_dir)
    out = json_artifact(project_dir, "visual_prompts.json")
    if not force and state.is_complete(StageName.PROMPTS) and out.exists():
        data = read_json(out)
        return [VisualPromptDetail.model_validate(p) for p in data["prompts"]]

    require_stage(project_dir, StageName.PROMPTS, StageName.SCENES)
    config = get_config(project_dir)
    scenes = ScenePlan.model_validate(read_json(json_artifact(project_dir, "scene_plan.json")))

    writer = GeminiLLMWriter(get_settings())
    style_ref_note = ""
    if config.style_reference:
        ref = project_dir / config.style_reference
        if ref.is_file():
            style_ref_note = (
                "Lock visuals to the reference image in inputs (Whisk-style style transfer). "
                "Same line weight, palette, and character proportions in every scene."
            )
    if config.character_reference:
        cref = project_dir / config.character_reference
        if cref.is_file():
            style_ref_note += " Use the character reference for identical face/expression each scene."

    style_raw = writer.generate_json(
        (
            "Create a style_bible JSON for consistent visuals across scenes: "
            "visual_style, palette, lighting, composition_rules, negative_global. "
            f"{style_ref_note}"
        ),
        {"visual_style": config.visual_style, "topic": config.topic},
        "StyleBible",
    )
    style = StyleBible.model_validate(style_raw)
    atomic_write_json(json_artifact(project_dir, "style_bible.json"), style.model_dump(mode="json"))

    prompts: list[VisualPromptDetail] = []
    for scene in scenes.scenes:
        raw = writer.generate_json(
            (
                "Expand scene into image prompt JSON: scene_id, subject, setting, composition, "
                "lighting, mood, palette, camera_framing, negative_prompt, aspect_ratio, full_prompt. "
                "full_prompt must be one paragraph ready for image model. "
                "Avoid floating objects, extra limbs, mismatched faces. "
                "Prefer simple MS Paint / editorial illustration compositions."
            ),
            {
                "scene": scene.model_dump(),
                "style_bible": style.model_dump(),
                "aspect_ratio": config.aspect_ratio,
            },
            "VisualPromptDetail",
        )
        detail = VisualPromptDetail.model_validate(raw)
        if not detail.full_prompt:
            detail = VisualPromptDetail(
                **{
                    **detail.model_dump(),
                    "full_prompt": f"{style.visual_style}. {scene.visual_prompt or scene.narration}",
                }
            )
        prompts.append(detail)

    atomic_write_json(out, {"prompts": [p.model_dump() for p in prompts]})
    state.mark_complete(StageName.PROMPTS, content_hash([p.model_dump() for p in prompts]))
    save_state(project_dir, state)
    return prompts
