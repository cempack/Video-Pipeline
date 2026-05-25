"""Retry transient API failures."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class PermanentError(Exception):
    """Non-retryable failure."""


def retry_transient(
    fn: Callable[[], T],
    *,
    max_attempts: int = 4,
    base_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except PermanentError:
            raise
        except retry_on as exc:
            last = exc
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2**attempt))
    raise last  # type: ignore[misc]
