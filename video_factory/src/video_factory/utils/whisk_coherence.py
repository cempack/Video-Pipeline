"""Whisk-style visual coherence: style transfer, palette lock, character face lock."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger("video_factory")


@dataclass
class WhiskReferences:
    style_reference: Path | None = None
    character_reference: Path | None = None
    character_sheet: Path | None = None


def load_references(project_dir: Path, config) -> WhiskReferences:
    style = _resolve_ref(project_dir, getattr(config, "style_reference", "") or "")
    char = _resolve_ref(project_dir, getattr(config, "character_reference", "") or "")
    sheet = project_dir / "work" / "json" / "character_sheet.png"
    if not sheet.is_file():
        sheet = char
    return WhiskReferences(style_reference=style, character_reference=char, character_sheet=sheet)


def _resolve_ref(project_dir: Path, rel: str) -> Path | None:
    if not rel:
        return None
    p = project_dir / rel
    return p if p.is_file() else None


def extract_palette(img: Image.Image, n_colors: int = 8) -> list[tuple[int, int, int]]:
    small = img.convert("RGB").resize((64, 64))
    quantized = small.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    if not palette:
        return [(32, 36, 48)]
    colors: list[tuple[int, int, int]] = []
    for i in range(0, min(n_colors * 3, len(palette)), 3):
        colors.append((palette[i], palette[i + 1], palette[i + 2]))
    return colors[:n_colors]


def apply_palette_harmonize(scene: Image.Image, style_ref: Image.Image, strength: float = 0.55) -> Image.Image:
    """Pull scene colors toward style-reference palette (Whisk-style consistency)."""
    palette = extract_palette(style_ref)
    if not palette:
        return scene
    base = scene.convert("RGB")
    w, h = base.size
    overlay = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(overlay)
    band = max(h // len(palette), 1)
    for i, color in enumerate(palette):
        draw.rectangle([0, i * band, w, min((i + 1) * band, h)], fill=color)
    blended = Image.blend(base, overlay, alpha=strength)
    return blended


def apply_style_texture(scene: Image.Image, style_ref: Image.Image, alpha: float = 0.12) -> Image.Image:
    """Blend style reference texture/line weight over the scene."""
    ref = style_ref.convert("RGB").resize(scene.size, Image.Resampling.LANCZOS)
    return Image.blend(scene.convert("RGB"), ref, alpha=alpha)


def lock_character_face(
    scene: Image.Image,
    character_ref: Image.Image,
    *,
    anchor: str = "left",
    scale: float = 0.42,
    face_lock_strength: float = 0.92,
) -> Image.Image:
    """
    Composite the canonical character onto every scene (Bog's face fix, automated).
    Uses the full character reference scaled to a fixed anchor so face/body stay identical.
    """
    canvas = scene.convert("RGBA")
    char = character_ref.convert("RGBA")

    target_h = int(canvas.height * scale)
    ratio = target_h / max(char.height, 1)
    target_w = int(char.width * ratio)
    char = char.resize((target_w, target_h), Image.Resampling.LANCZOS)

    margin_x = int(canvas.width * 0.06)
    margin_y = int(canvas.height * 0.22)
    if anchor == "center":
        x = (canvas.width - target_w) // 2
    else:
        x = margin_x
    y = canvas.height - target_h - margin_y

    # Soft mask from alpha channel
    mask = char.split()[3] if char.mode == "RGBA" else None
    canvas.paste(char, (x, y), mask)

    if face_lock_strength < 1.0:
        canvas = Image.blend(scene.convert("RGBA"), canvas, alpha=face_lock_strength)
    return canvas.convert("RGB")


def sharpen_pixel_style(img: Image.Image, style_ref: Image.Image | None = None) -> Image.Image:
    """Optional crisp edges reminiscent of MS Paint / pixel illustration."""
    out = img.convert("RGB")
    if style_ref:
        # If style ref has hard edges, nudge contrast
        out = ImageEnhance.Contrast(out).enhance(1.08)
    out = out.filter(ImageFilter.SHARPEN)
    return out


def postprocess_scene(
    image_path: Path,
    refs: WhiskReferences,
    *,
    face_lock: bool = True,
    palette_lock: bool = True,
    texture_lock: bool = True,
) -> None:
    """Apply full Whisk-style post pipeline to a generated scene PNG."""
    img = Image.open(image_path).convert("RGB")
    style = None
    if refs.style_reference and refs.style_reference.is_file():
        style = Image.open(refs.style_reference).convert("RGB")
    char = None
    char_path = refs.character_sheet or refs.character_reference
    if char_path and char_path.is_file():
        char = Image.open(char_path).convert("RGBA")

    if style and palette_lock:
        img = apply_palette_harmonize(img, style)
    if style and texture_lock:
        img = apply_style_texture(img, style)
    if char and face_lock:
        img = lock_character_face(img, char)
    if style:
        img = sharpen_pixel_style(img, style)

    img.save(image_path, format="PNG")
    logger.debug("Whisk postprocess applied to %s", image_path)


def build_whisk_prompt(scene_prompt: str, visual_style: str) -> str:
    return (
        "WHISK-STYLE IMAGE GENERATION RULES:\n"
        f"- Art style lock: {visual_style}\n"
        "- Copy the EXACT line weight, palette, and pixel/brush style from the STYLE reference image.\n"
        "- Copy the EXACT character face, hair, proportions, and expression from the CHARACTER reference.\n"
        "- Do NOT redesign the character. Do NOT change facial features between scenes.\n"
        "- Simple composition, static illustration, no photorealism, no 3D render look.\n"
        "- No floating objects, no extra limbs, no melted faces.\n"
        f"SCENE: {scene_prompt}"
    )
