"""Filesystem helpers for per-project artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def work_path(project_dir: Path, *parts: str) -> Path:
    return project_dir.joinpath("work", *parts)


def outputs_path(project_dir: Path, *parts: str) -> Path:
    return project_dir.joinpath("outputs", *parts)


def inputs_path(project_dir: Path, *parts: str) -> Path:
    return project_dir.joinpath("inputs", *parts)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_file(path: Path, label: str = "file") -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"Required {label} not found: {path}")
    return path
