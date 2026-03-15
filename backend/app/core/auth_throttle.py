"""IP-based authentication failure throttling.

Tracks failed auth attempts per IP address using a sliding window.
After exceeding the threshold, the IP is locked out for the configured duration.

Set RATE_LIMIT_STORAGE_URI to a Redis URL for multi-instance deployments.
Falls back to in-memory when unset.
"""

from __future__ import annotations

import threading
import time
from typing import Protocol

from app.core.config import settings


class AuthThrottleBackend(Protocol):
    """Interface for auth throttle storage backends."""

    def record_failure(self, ip: str) -> None: ...
    def record_success(self, ip: str) -> None: ...
    def is_locked_out(self, ip: str) -> bool: ...


class InMemoryAuthThrottle:
    """Sliding-window rate limiter using in-memory dict (single-instance only)."""

    def __init__(self, threshold: int, window_seconds: int) -> None:
        self._threshold = threshold
        self._window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def record_failure(self, ip: str) -> None:
        now = time.monotonic()
        with self._lock:
            timestamps = self._failures.get(ip, [])
            timestamps.append(now)
            cutoff = now - self._window_seconds
            self._failures[ip] = [t for t in timestamps if t > cutoff]

    def record_success(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)

    def is_locked_out(self, ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            timestamps = self._failures.get(ip)
            if timestamps is None:
                return False
            cutoff = now - self._window_seconds
            recent = [t for t in timestamps if t > cutoff]
            self._failures[ip] = recent
            return len(recent) >= self._threshold


class RedisAuthThrottle:
    """Sliding-window rate limiter backed by Redis sorted sets."""

    def __init__(self, threshold: int, window_seconds: int, redis_url: str) -> None:
        import redis

        self._threshold = threshold
        self._window_seconds = window_seconds
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "auth_throttle:"

    def _key(self, ip: str) -> str:
        return f"{self._prefix}{ip}"

    def record_failure(self, ip: str) -> None:
        now = time.time()
        key = self._key(ip)
        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.zremrangebyscore(key, 0, now - self._window_seconds)
        pipe.expire(key, self._window_seconds)
        pipe.execute()

    def record_success(self, ip: str) -> None:
        self._redis.delete(self._key(ip))

    def is_locked_out(self, ip: str) -> bool:
        now = time.time()
        key = self._key(ip)
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self._window_seconds)
        pipe.zcard(key)
        results = pipe.execute()
        return int(results[1]) >= self._threshold


def _create_throttle() -> AuthThrottleBackend:
    threshold = settings.auth_lockout_threshold
    window = settings.auth_lockout_window_minutes * 60
    redis_url = settings.rate_limit_storage_uri
    if redis_url:
        return RedisAuthThrottle(threshold, window, redis_url)
    return InMemoryAuthThrottle(threshold, window)


auth_throttle: AuthThrottleBackend = _create_throttle()
