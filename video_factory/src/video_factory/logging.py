"""Structured logging helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(project_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("video_factory")
    logger.setLevel(level)
    if logger.handlers:
        return logger

    console_handler = RichHandler(console=Console(stderr=True), show_path=False)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    if project_dir:
        log_dir = project_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(file_handler)

    return logger
