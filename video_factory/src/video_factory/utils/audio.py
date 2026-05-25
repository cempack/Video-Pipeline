"""Audio post-processing inspired by faceless-channel workflows."""

from __future__ import annotations

import random
import subprocess
from pathlib import Path


def remove_silence_ffmpeg(
    ffmpeg_bin: str,
    input_path: Path,
    output_path: Path,
    *,
    threshold_db: float = -40.0,
    min_silence_sec: float = 0.15,
) -> Path:
    """Strip quiet gaps from TTS (clean AI voiceovers have clear pauses)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # silenceremove: drop stretches below threshold
    af = (
        f"silenceremove=start_periods=1:start_threshold={threshold_db}dB:"
        f"start_duration={min_silence_sec}:"
        f"stop_periods=-1:stop_threshold={threshold_db}dB:"
        f"stop_duration={min_silence_sec}"
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-af",
        af,
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"silenceremove failed: {proc.stderr[-1500:]}")
    return output_path


def apply_subtle_loudness_variation(
    ffmpeg_bin: str,
    input_path: Path,
    output_path: Path,
    *,
    seed: int | None = None,
) -> Path:
    """Slight per-scene level drift so narration is not perfectly flat."""
    rng = random.Random(seed)
    # ±1.5 dB random offset, then normalize lightly
    offset_db = rng.uniform(-1.5, 1.5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    af = f"volume={offset_db}dB,loudnorm=I=-16:TP=-1.5:LRA=11"
    cmd = [ffmpeg_bin, "-y", "-i", str(input_path), "-af", af, str(output_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"loudness variation failed: {proc.stderr[-1500:]}")
    return output_path
