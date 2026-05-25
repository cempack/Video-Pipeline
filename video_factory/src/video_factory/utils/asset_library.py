"""Reusable image library across projects (Bog-style asset index)."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_factory.models.schemas import LibraryAsset, LibraryIndex
from video_factory.utils.files import atomic_write_json, read_json


def default_library_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "library"


def library_index_path(library_dir: Path) -> Path:
    return library_dir / "index.json"


def load_library(library_dir: Path) -> LibraryIndex:
    path = library_index_path(library_dir)
    if not path.exists():
        return LibraryIndex()
    return LibraryIndex.model_validate(read_json(path))


def save_library(library_dir: Path, index: LibraryIndex) -> None:
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / "assets").mkdir(exist_ok=True)
    atomic_write_json(library_index_path(library_dir), index.model_dump(mode="json"))


def find_library_match(
    index: LibraryIndex,
    prompt: str,
    visual_style: str,
) -> LibraryAsset | None:
    """Simple keyword overlap match; prefer same style tag."""
    prompt_l = prompt.lower()
    best: LibraryAsset | None = None
    best_score = 0
    for asset in index.assets:
        desc_l = asset.description.lower()
        score = sum(1 for w in desc_l.split() if len(w) > 3 and w in prompt_l)
        if asset.style and asset.style.lower() in visual_style.lower():
            score += 2
        if score > best_score:
            best_score = score
            best = asset
    return best if best_score >= 2 else None


def register_asset(
    library_dir: Path,
    source_image: Path,
    description: str,
    *,
    tags: list[str] | None = None,
    style: str = "",
) -> LibraryAsset:
    index = load_library(library_dir)
    asset_id = f"lib_{len(index.assets) + 1:04d}"
    dest = library_dir / "assets" / f"{asset_id}{source_image.suffix or '.png'}"
    shutil.copy2(source_image, dest)
    rel = str(dest.relative_to(library_dir))
    entry = LibraryAsset(
        asset_id=asset_id,
        description=description,
        path=rel,
        tags=tags or [],
        style=style,
    )
    index.assets.append(entry)
    save_library(library_dir, index)
    return entry
