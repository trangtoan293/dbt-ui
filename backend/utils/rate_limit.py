"""In-memory per-user sliding-window rate limiter."""
import time
from collections import defaultdict, deque
from fastapi import HTTPException


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float, now=time.time):
        self._max = max_calls
        self._window = window_seconds
        self._now = now
        self._calls = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self._now()
        q = self._calls[key]
        while q and q[0] <= now - self._window:
            q.popleft()
        if len(q) >= self._max:
            raise HTTPException(status_code=429, detail="Too many requests")
        q.append(now)
