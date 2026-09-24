from __future__ import annotations

import asyncio
import time
from collections.abc import Callable


class FixedWindowRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = self._clock()
        async with self._lock:
            window_started, count = self._windows.get(key, (now, 0))
            if now - window_started >= self.window_seconds:
                window_started, count = now, 0
            if count >= self.limit:
                return False
            self._windows[key] = (window_started, count + 1)
            return True
