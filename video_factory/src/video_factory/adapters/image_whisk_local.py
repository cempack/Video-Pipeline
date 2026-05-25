"""Local Whisk-style pipeline without API: generate base + coherence postprocess."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from video_factory.models.schemas import VisualPromptDetail
from video_factory.utils.whisk_coherence import WhiskReferences, postprocess_scene

logger = logging.getLogger("video_factory")


class WhiskLocalImageProvider:
    """Placeholder base art + full palette/character lock (offline Whisk mimic)."""

    def __init__(self, refs: WhiskReferences, visual_style: str = "") -> None:
        self._refs = refs
        self._visual_style = visual_style

    def generate(
        self,
        prompt: VisualPromptDetail,
        output_path: Path,
        width: int,
        height: int,
        seed: int | None = None,
    ) -> dict:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        bg = (240, 248, 255)
        if self._refs.style_reference and self._refs.style_reference.is_file():
            style = Image.open(self._refs.style_reference).convert("RGB")
            bg_img = style.resize((width, height), Image.Resampling.LANCZOS)
            img = Image.blend(Image.new("RGB", (width, height), bg), bg_img, alpha=0.35)
        else:
            img = Image.new("RGB", (width, height), color=bg)

        draw = ImageDraw.Draw(img)
        label = prompt.scene_id
        body = (prompt.full_prompt or prompt.subject or label)[:120]
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.rounded_rectangle([48, height // 3, width - 48, height // 3 + 120], radius=12, outline=(60, 70, 90), width=2)
        draw.text((64, height // 3 + 12), label, fill=(30, 35, 50), font=font)
        draw.text((64, height // 3 + 36), body, fill=(50, 55, 70), font=font)
        img.save(output_path, format="PNG")

        postprocess_scene(output_path, self._refs, face_lock=True, palette_lock=True, texture_lock=True)
        return {
            "path": str(output_path),
            "model": "whisk_local",
            "seed": seed,
            "width": width,
            "height": height,
            "backend": "whisk_local",
        }
