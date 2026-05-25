"""Whisk coherence and face lock tests."""

from pathlib import Path

from PIL import Image

from video_factory.utils.whisk_coherence import (
    WhiskReferences,
    apply_palette_harmonize,
    build_whisk_prompt,
    lock_character_face,
    postprocess_scene,
)


def test_build_whisk_prompt_mentions_character():
    p = build_whisk_prompt("stickman in forest", "MS Paint")
    assert "CHARACTER" in p or "character" in p.lower()
    assert "forest" in p


def test_palette_harmonize_changes_pixels(tmp_path: Path):
    style = Image.new("RGB", (100, 100), (255, 0, 0))
    scene = Image.new("RGB", (100, 100), (0, 0, 255))
    out = apply_palette_harmonize(scene, style, strength=0.8)
    assert out.getpixel((50, 50)) != scene.getpixel((50, 50))


def test_face_lock_composites_character(tmp_path: Path):
    scene = Image.new("RGB", (400, 600), (200, 200, 200))
    char = Image.new("RGBA", (200, 300), (255, 0, 0, 255))
    locked = lock_character_face(scene, char, scale=0.35)
    # Character anchored lower-left — pixel should differ from flat gray background
    assert locked.getpixel((50, 420)) != (200, 200, 200)


def test_postprocess_writes_file(tmp_path: Path):
    style = tmp_path / "style.png"
    char = tmp_path / "char.png"
    out = tmp_path / "scene.png"
    Image.new("RGB", (200, 300), (10, 20, 30)).save(style)
    Image.new("RGBA", (120, 180), (255, 200, 150, 255)).save(char)
    Image.new("RGB", (1080, 1920), (128, 128, 128)).save(out)
    refs = WhiskReferences(style_reference=style, character_reference=char)
    postprocess_scene(out, refs)
    assert out.stat().st_size > 0
