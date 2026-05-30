import pytest
from fastapi import HTTPException
from utils.rate_limit import RateLimiter


def test_allows_up_to_limit():
    rl = RateLimiter(max_calls=3, window_seconds=60, now=lambda: 1000.0)
    for _ in range(3):
        rl.check("user-a")  # no raise


def test_blocks_over_limit():
    rl = RateLimiter(max_calls=3, window_seconds=60, now=lambda: 1000.0)
    for _ in range(3):
        rl.check("user-a")
    with pytest.raises(HTTPException) as e:
        rl.check("user-a")
    assert e.value.status_code == 429


def test_window_resets():
    t = {"v": 1000.0}
    rl = RateLimiter(max_calls=1, window_seconds=10, now=lambda: t["v"])
    rl.check("user-a")
    t["v"] = 1011.0
    rl.check("user-a")  # window passed, allowed again


def test_users_isolated():
    rl = RateLimiter(max_calls=1, window_seconds=60, now=lambda: 1000.0)
    rl.check("user-a")
    rl.check("user-b")  # different user, allowed
