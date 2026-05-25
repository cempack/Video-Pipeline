"""Image generation per scene."""

from __future__ import annotations

from pathlib import Path

from video_factory.adapters.image_provider import get_image_provider
from video_factory.models.schemas import AssetManifest, ImageAsset, StageName, VisualPromptDetail
from video_factory.stages.base import aspect_dimensions, get_config, get_settings, json_artifact, load_state, require_stage, save_state
from video_factory.utils.files import atomic_write_json, read_json, work_path
from video_factory.utils.hash import content_hash


def run_images(project_dir: Path, *, force: bool = False) -> AssetManifest:
    state = load_state(project_dir)
    manifest_path = json_artifact(project_dir, "asset_manifest.json")
    if not force and state.is_complete(StageName.IMAGES) and manifest_path.exists():
        return AssetManifest.model_validate(read_json(manifest_path))

    require_stage(project_dir, StageName.IMAGES, StageName.PROMPTS)
    config = get_config(project_dir)
    width, height = aspect_dimensions(config.aspect_ratio)
    prompts_data = read_json(json_artifact(project_dir, "visual_prompts.json"))
    prompts = [VisualPromptDetail.model_validate(p) for p in prompts_data["prompts"]]

    provider = get_image_provider(get_settings())
    images: list[ImageAsset] = []
    for p in prompts:
        out_rel = f"work/images/{p.scene_id}.png"
        out_path = project_dir / out_rel
        cache_key = content_hash({"prompt": p.full_prompt, "w": width, "h": height})
        if out_path.exists() and not force:
            images.append(
                ImageAsset(
                    scene_id=p.scene_id,
                    prompt=p.full_prompt,
                    path=out_rel,
                    width=width,
                    height=height,
                )
            )
            continue
        meta = provider.generate(p, out_path, width, height, seed=hash(cache_key) % 2_147_483_647)
        images.append(
            ImageAsset(
                scene_id=p.scene_id,
                prompt=p.full_prompt,
                path=out_rel,
                seed=meta.get("seed"),
                model=meta.get("model", ""),
                width=width,
                height=height,
            )
        )

    manifest = AssetManifest(images=images)
    if manifest_path.exists():
        existing = AssetManifest.model_validate(read_json(manifest_path))
        manifest = AssetManifest(
            images=images,
            audio=existing.audio,
            subtitles=existing.subtitles,
        )
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))
    state.mark_complete(StageName.IMAGES, content_hash(manifest.model_dump()))
    save_state(project_dir, state)
    return manifest
