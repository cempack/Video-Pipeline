"""Content hashing for cache keys."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash(payload: Any) -> str:
    if isinstance(payload, (dict, list)):
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    else:
        raw = str(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
