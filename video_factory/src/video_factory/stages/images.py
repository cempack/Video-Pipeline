"""Image generation: variants per scene, library reuse, batch prompts."""

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
from video_factory.stages.base import aspect_dimensions, get_config, get_settings, json_artifact, load_state, require_stage, save_state
from video_factory.utils.asset_library import default_library_dir, find_library_match, load_library
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash


def run_images(project_dir: Path, *, force: bool = False) -> AssetManifest:
    state = load_state(project_dir)
    manifest_path = json_artifact(project_dir, "asset_manifest.json")
    candidates_path = json_artifact(project_dir, "image_candidates.json")

    if not force and state.is_complete(StageName.IMAGES) and manifest_path.exists():
        return AssetManifest.model_validate(read_json(manifest_path))

    require_stage(project_dir, StageName.IMAGES, StageName.PROMPTS)
    config = get_config(project_dir)
    width, height = aspect_dimensions(config.aspect_ratio)
    prompts_data = read_json(json_artifact(project_dir, "visual_prompts.json"))
    prompts = [VisualPromptDetail.model_validate(p) for p in prompts_data["prompts"]]

    # Optional batch file: one prompt line per scene (auto-whisk style)
    batch_file = project_dir / "inputs" / "batch_image_prompts.txt"
    if batch_file.exists():
        lines = [ln.strip() for ln in batch_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for i, p in enumerate(prompts):
            if i < len(lines):
                p = VisualPromptDetail(**{**p.model_dump(), "full_prompt": lines[i]})
                prompts[i] = p

    style_ref = None
    if config.style_reference:
        candidate = project_dir / config.style_reference
        if candidate.is_file():
            style_ref = candidate
    provider = get_image_provider(get_settings(), style_reference=style_ref)
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
                variants.append(ImageVariant(variant_id="v01", path=str(canonical.relative_to(project_dir))))
                reused = True

        if not reused:
            for v in range(1, n_variants + 1):
                vid = f"v{v:02d}"
                out_rel = f"work/images/{p.scene_id}_{vid}.png"
                out_path = project_dir / out_rel
                cache_key = content_hash({"prompt": p.full_prompt, "w": width, "h": height, "v": v})
                if out_path.exists() and not force:
                    variants.append(ImageVariant(variant_id=vid, path=out_rel))
                    continue
                seed = hash(cache_key) % 2_147_483_647
                provider.generate(p, out_path, width, height, seed=seed)
                variants.append(ImageVariant(variant_id=vid, path=out_rel, seed=seed))

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
        sel_path = f"work/images/{p.scene_id}.png"
        images.append(
            ImageAsset(
                scene_id=p.scene_id,
                prompt=p.full_prompt,
                path=sel_path,
                width=width,
                height=height,
                variant_id=selected or "",
                from_library=reused,
            )
        )

    selection = ImageSelectionManifest(scenes=candidate_sets)
    atomic_write_json(candidates_path, selection.model_dump(mode="json"))

    manifest = AssetManifest(images=images)
    if manifest_path.exists():
        existing = AssetManifest.model_validate(read_json(manifest_path))
        manifest = AssetManifest(images=images, audio=existing.audio, subtitles=existing.subtitles)
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))
    state.mark_complete(StageName.IMAGES, content_hash(manifest.model_dump()))
    save_state(project_dir, state)
    return manifest


def select_image_variant(project_dir: Path, scene_id: str, variant_id: str) -> ImageAsset:
    """Pick one of N generated variants (human-in-the-loop quality gate)."""
    candidates_path = json_artifact(project_dir, "image_candidates.json")
    if not candidates_path.exists():
        raise FileNotFoundError("Run images stage first to generate candidates")
    selection = ImageSelectionManifest.model_validate(read_json(candidates_path))
    manifest_path = json_artifact(project_dir, "asset_manifest.json")
    manifest = AssetManifest.model_validate(read_json(manifest_path))

    target_set = next((s for s in selection.scenes if s.scene_id == scene_id), None)
    if not target_set:
        raise ValueError(f"Unknown scene_id: {scene_id}")

    variant = next((v for v in target_set.variants if v.variant_id == variant_id), None)
    if not variant:
        raise ValueError(f"Unknown variant {variant_id} for {scene_id}")

    _promote_variant(project_dir, scene_id, variant.path)
    target_set.selected_variant_id = variant_id

    for i, img in enumerate(manifest.images):
        if img.scene_id == scene_id:
            manifest.images[i] = ImageAsset(
                **{
                    **img.model_dump(),
                    "path": f"work/images/{scene_id}.png",
                    "variant_id": variant_id,
                }
            )
            break

    atomic_write_json(candidates_path, selection.model_dump(mode="json"))
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))
    return manifest.images[[img.scene_id for img in manifest.images].index(scene_id)]


def _promote_variant(project_dir: Path, scene_id: str, variant_path: str) -> None:
    src = project_dir / variant_path
    dst = project_dir / f"work/images/{scene_id}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
