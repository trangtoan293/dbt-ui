"""In-memory per-user sliding-window rate limiter.

NOTE: Single-process only. In a multi-worker deployment each worker maintains
its own state, making the effective limit max_calls * num_workers. Use a shared
backend (e.g. Redis) for multi-worker enforcement.
"""
import time
from collections import defaultdict, deque
from fastapi import HTTPException

_MAX_TRACKED_KEYS = 10_000  # cap memory; evict oldest key when exceeded


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float, now=time.time):
        self._max = max_calls
        self._window = window_seconds
        self._now = now
        self._calls: dict[str, deque] = {}

    def check(self, key: str) -> None:
        now = self._now()
        if key not in self._calls:
            if len(self._calls) >= _MAX_TRACKED_KEYS:
                # Evict an arbitrary entry to bound memory
                self._calls.pop(next(iter(self._calls)))
            self._calls[key] = deque()
        q = self._calls[key]
        while q and q[0] <= now - self._window:
            q.popleft()
        if len(q) >= self._max:
            raise HTTPException(status_code=429, detail="Too many requests")
        q.append(now)
