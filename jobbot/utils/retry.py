from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


def retry(
    operation: Callable[[], T],
    attempts: int = 3,
    delay_seconds: float = 1.0,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == attempts:
                break
            if on_retry is not None:
                on_retry(attempt, exc)
            time.sleep(delay_seconds)
    if last_error is None:
        raise RuntimeError("Retry operation failed without an exception.")
    raise last_error
