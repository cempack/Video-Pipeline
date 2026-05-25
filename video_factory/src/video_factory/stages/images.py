"""Image generation: Whisk coherence, variants, library reuse."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_factory.adapters.image_provider import get_image_provider
from video_factory.models.schemas import (
    AssetManifest,
    ImageAsset,
    ImageCandidateSet,
    ImageSelectionManifest,
    ImageVariant,
    StageName,
    VisualPromptDetail,
)
from video_factory.stages.base import (
    aspect_dimensions,
    get_config,
    get_settings,
    json_artifact,
    load_state,
    require_stage,
    save_state,
)
from video_factory.stages.character import run_character_sheet
from video_factory.utils.asset_library import default_library_dir, find_library_match, load_library
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash
from video_factory.utils.whisk_coherence import load_references, postprocess_scene


def run_images(project_dir: Path, *, force: bool = False) -> AssetManifest:
    state = load_state(project_dir)
    manifest_path = json_artifact(project_dir, "asset_manifest.json")
    candidates_path = json_artifact(project_dir, "image_candidates.json")

    if not force and state.is_complete(StageName.IMAGES) and manifest_path.exists():
        return AssetManifest.model_validate(read_json(manifest_path))

    require_stage(project_dir, StageName.IMAGES, StageName.PROMPTS)
    config = get_config(project_dir)

    if config.enforce_face_lock:
        run_character_sheet(project_dir, force=force)

    width, height = aspect_dimensions(config.aspect_ratio)
    prompts_data = read_json(json_artifact(project_dir, "visual_prompts.json"))
    prompts = [VisualPromptDetail.model_validate(p) for p in prompts_data["prompts"]]

    batch_file = project_dir / "inputs" / "batch_image_prompts.txt"
    if batch_file.exists():
        lines = [ln.strip() for ln in batch_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for i, p in enumerate(prompts):
            if i < len(lines):
                prompts[i] = VisualPromptDetail(**{**p.model_dump(), "full_prompt": lines[i]})

    provider = get_image_provider(get_settings(), config, project_dir)
    refs = load_references(project_dir, config)
    library_dir = default_library_dir()
    library = load_library(library_dir) if config.use_asset_library else None

    candidate_sets: list[ImageCandidateSet] = []
    images: list[ImageAsset] = []
    n_variants = config.image_variants_per_scene

    for p in prompts:
        variants: list[ImageVariant] = []
        reused = False

        if library and config.use_asset_library:
            match = find_library_match(library, p.full_prompt, config.visual_style)
            if match and (library_dir / match.path).is_file():
                canonical = project_dir / f"work/images/{p.scene_id}.png"
                canonical.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(library_dir / match.path, canonical)
                postprocess_scene(canonical, refs, face_lock=config.enforce_face_lock)
                for v in range(1, n_variants + 1):
                    vid = f"v{v:02d}"
                    variants.append(
                        ImageVariant(variant_id=vid, path=f"work/images/{p.scene_id}_{vid}.png")
                    )
                    shutil.copy2(canonical, project_dir / variants[-1].path)
                reused = True

        if not reused:
            for v in range(1, n_variants + 1):
                vid = f"v{v:02d}"
                out_rel = f"work/images/{p.scene_id}_{vid}.png"
                out_path = project_dir / out_rel
                cache_key = content_hash({"prompt": p.full_prompt, "w": width, "h": height, "v": v})
                if out_path.exists() and not force:
                    variants.append(ImageVariant(variant_id=vid, path=out_rel))
                else:
                    seed = hash(cache_key) % 2_147_483_647
                    provider.generate(p, out_path, width, height, seed=seed)
                    variants.append(ImageVariant(variant_id=vid, path=out_rel, seed=seed))
                postprocess_scene(out_path, refs, face_lock=config.enforce_face_lock)

        selected = variants[0].variant_id if variants else None
        if config.auto_select_first_variant and variants:
            _promote_variant(project_dir, p.scene_id, variants[0].path)
        candidate_sets.append(
            ImageCandidateSet(
                scene_id=p.scene_id,
                prompt=p.full_prompt,
                variants=variants,
                selected_variant_id=selected,
            )
        )
        images.append(
            ImageAsset(
                scene_id=p.scene_id,
                prompt=p.full_prompt,
                path=f"work/images/{p.scene_id}.png",
                width=width,
                height=height,
                variant_id=selected or "",
                from_library=reused,
            )
        )

    atomic_write_json(candidates_path, ImageSelectionManifest(scenes=candidate_sets).model_dump(mode="json"))

    manifest = AssetManifest(images=images)
    if manifest_path.exists():
        existing = AssetManifest.model_validate(read_json(manifest_path))
        manifest = AssetManifest(images=images, audio=existing.audio, subtitles=existing.subtitles)
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))
    state.mark_complete(StageName.IMAGES, content_hash(manifest.model_dump()))
    save_state(project_dir, state)
    return manifest


def select_image_variant(project_dir: Path, scene_id: str, variant_id: str) -> ImageAsset:
    candidates_path = json_artifact(project_dir, "image_candidates.json")
    if not candidates_path.exists():
        raise FileNotFoundError("Run images stage first to generate candidates")
    selection = ImageSelectionManifest.model_validate(read_json(candidates_path))
    manifest_path = json_artifact(project_dir, "asset_manifest.json")
    manifest = AssetManifest.model_validate(read_json(manifest_path)) if manifest_path.exists() else AssetManifest()

    target_set = next((s for s in selection.scenes if s.scene_id == scene_id), None)
    if not target_set:
        raise ValueError(f"Unknown scene_id: {scene_id}")

    variant = next((v for v in target_set.variants if v.variant_id == variant_id), None)
    if not variant:
        raise ValueError(f"Unknown variant {variant_id} for {scene_id}")

    _promote_variant(project_dir, scene_id, variant.path)
    target_set.selected_variant_id = variant_id

    updated: ImageAsset | None = None
    found = False
    for i, img in enumerate(manifest.images):
        if img.scene_id == scene_id:
            updated = ImageAsset(
                **{
                    **img.model_dump(),
                    "path": f"work/images/{scene_id}.png",
                    "variant_id": variant_id,
                }
            )
            manifest.images[i] = updated
            found = True
            break
    if not found:
        updated = ImageAsset(scene_id=scene_id, prompt=target_set.prompt, path=f"work/images/{scene_id}.png", variant_id=variant_id)
        manifest.images.append(updated)

    config = get_config(project_dir)
    refs = load_references(project_dir, config)
    postprocess_scene(project_dir / f"work/images/{scene_id}.png", refs, face_lock=config.enforce_face_lock)

    atomic_write_json(candidates_path, selection.model_dump(mode="json"))
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))
    return updated  # type: ignore[return-value]


def _promote_variant(project_dir: Path, scene_id: str, variant_path: str) -> None:
    src = project_dir / variant_path
    dst = project_dir / f"work/images/{scene_id}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
