"""Thread-safe circuit breaker — W15 G11.

Implements the classic three-state circuit breaker:

``CLOSED``   — normal operation; calls pass through.
``OPEN``     — fail-fast; calls raise :exc:`CircuitOpenError` immediately.
             Transitions to ``HALF_OPEN`` after *reset_timeout* seconds.
``HALF_OPEN``— probe state; the next call is attempted.
             Success → ``CLOSED``; failure → ``OPEN`` (reset timer restarts).

Usage::

    cb = CircuitBreaker(threshold=3, reset_timeout=30, name="inventory")

    try:
        result = cb.call(requests.get, "http://inventory/api/drones")
    except CircuitOpenError:
        result = _cached_fallback()
    except Exception:
        # original exception propagated; failure was recorded
        raise
"""

from __future__ import annotations

import threading
import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""


class CircuitBreaker:
    """Sync, thread-safe circuit breaker.

    Parameters
    ----------
    threshold:
        Number of consecutive failures that flip the circuit OPEN.
    reset_timeout:
        Seconds to wait in OPEN state before allowing a probe (HALF_OPEN).
    name:
        Human-readable name used in error messages and logs.
    """

    def __init__(
        self,
        *,
        threshold: int = 3,
        reset_timeout: float = 30.0,
        name: str = "default",
    ) -> None:
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.name = name

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Return the current state, auto-advancing OPEN → HALF_OPEN on timeout."""
        with self._lock:
            return self._current_state()

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def call(self, fn, /, *args, **kwargs):
        """Execute *fn* through the circuit breaker.

        Raises
        ------
        CircuitOpenError
            If the circuit is currently OPEN.
        Exception
            The original exception from *fn* if the call fails (failure is
            recorded before re-raising).
        """
        with self._lock:
            state = self._current_state()
            if state == CircuitState.OPEN:
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is OPEN — call rejected"
                )
            # HALF_OPEN: allow the call but track as a probe

        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise

        self._on_success()
        return result

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    # ------------------------------------------------------------------
    # Internal helpers (must be called with _lock held where noted)
    # ------------------------------------------------------------------

    def _current_state(self) -> CircuitState:
        """Compute effective state; may promote OPEN → HALF_OPEN. Needs _lock."""
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def _on_success(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.threshold:
                self._state = CircuitState.OPEN
