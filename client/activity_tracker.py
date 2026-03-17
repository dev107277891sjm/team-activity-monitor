"""Tracks last keyboard/mouse activity for IDLE/REST status."""
import threading
import time


class ActivityTracker:
    """Thread-safe tracker of last user activity (keyboard/mouse)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_activity = time.time()
        self._last_keyboard_activity = time.time()

    def update(self) -> None:
        """Record that activity just occurred. Throttled to avoid mouse-move spam."""
        now = time.time()
        with self._lock:
            if now - self._last_activity < 1.0:
                return
            self._last_activity = now

    def update_keyboard(self) -> None:
        """Record that keyboard activity just occurred."""
        with self._lock:
            self._last_keyboard_activity = time.time()
            self._last_activity = self._last_keyboard_activity

    def get_idle_seconds(self) -> float:
        """Return seconds since last activity."""
        with self._lock:
            return time.time() - self._last_activity

    def get_keyboard_idle_seconds(self) -> float:
        """Return seconds since last keyboard activity."""
        with self._lock:
            return time.time() - self._last_keyboard_activity
