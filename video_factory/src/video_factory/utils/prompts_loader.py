"""Load optional markdown skill/instruction files from project inputs."""

from __future__ import annotations

from pathlib import Path


def load_project_instructions(project_dir: Path) -> dict[str, str]:
    """Load inputs/*.md instruction files (script, scenes, images, etc.)."""
    inputs = project_dir / "inputs"
    if not inputs.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in sorted(inputs.glob("*.md")):
        if path.name == "notes.md":
            continue
        key = path.stem
        text = path.read_text(encoding="utf-8").strip()
        if text:
            out[key] = text
    return out


def merge_instruction(base: str, extras: dict[str, str], key: str) -> str:
    extra = extras.get(key, "")
    if not extra:
        return base
    return f"{base}\n\nProject instructions ({key}.md):\n{extra}"
