"""In-memory IP-based authentication failure throttling.

Tracks failed auth attempts per IP address using a sliding window.
After exceeding the threshold, the IP is locked out for the configured duration.

Phase 1: in-memory dict (single-instance). Swap to Redis for multi-instance.
"""

import threading
import time

from app.core.config import settings


class AuthThrottle:
    """Sliding-window rate limiter for failed authentication attempts."""

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
            # Keep only timestamps within the window
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


auth_throttle = AuthThrottle(
    threshold=settings.auth_lockout_threshold,
    window_seconds=settings.auth_lockout_window_minutes * 60,
)
