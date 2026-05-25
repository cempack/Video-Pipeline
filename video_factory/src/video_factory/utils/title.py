"""YouTube title / hook validation helpers."""

from __future__ import annotations


def title_fits_homepage(title: str, max_chars: int = 60) -> tuple[bool, str]:
    length = len(title.strip())
    if length <= max_chars:
        return True, f"{length} chars (max {max_chars})"
    return False, f"{length} chars exceeds max {max_chars} for mobile homepage"


def hook_word_budget(target_duration_sec: float, hook_sec: float = 3.0, wpm: float = 145.0) -> int:
    return max(int(hook_sec * wpm / 60), 5)
