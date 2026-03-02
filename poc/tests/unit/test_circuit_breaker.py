"""Unit tests: CircuitBreaker — W15 G11.

Coverage:
  - CLOSED → normal calls pass through; return value forwarded
  - 3 consecutive failures → OPEN; next call raises CircuitOpenError
  - OPEN → after reset_timeout → HALF_OPEN; successful probe → CLOSED
  - HALF_OPEN → failure → OPEN (reset timer restarts)
  - manual reset() → CLOSED
  - failure_count resets on success
  - threshold=1 opens on first failure
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from poc.v4_mission_control.infra.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cb(**kwargs) -> CircuitBreaker:
    defaults = {"threshold": 3, "reset_timeout": 30.0, "name": "test"}
    defaults.update(kwargs)
    return CircuitBreaker(**defaults)


def _fail(cb: CircuitBreaker, n: int = 1) -> None:
    """Make *n* failing calls (raises, but we swallow them)."""
    for _ in range(n):
        with pytest.raises(Exception):
            cb.call(_boom)


def _boom(*args, **kwargs):
    raise RuntimeError("simulated failure")


def _ok(*args, **kwargs):
    return "success"


# ---------------------------------------------------------------------------
# CLOSED state — normal operation
# ---------------------------------------------------------------------------


class TestClosed:
    def test_initial_state_is_closed(self):
        cb = _cb()
        assert cb.state == CircuitState.CLOSED

    def test_successful_call_passes_through(self):
        cb = _cb()
        result = cb.call(lambda: 42)
        assert result == 42

    def test_one_failure_does_not_open(self):
        cb = _cb(threshold=3)
        _fail(cb)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1

    def test_two_failures_do_not_open(self):
        cb = _cb(threshold=3)
        _fail(cb, 2)
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        cb = _cb(threshold=3)
        _fail(cb, 2)
        cb.call(_ok)
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# CLOSED → OPEN transition
# ---------------------------------------------------------------------------


class TestOpenTransition:
    def test_threshold_failures_open_circuit(self):
        cb = _cb(threshold=3)
        _fail(cb, 3)
        assert cb.state == CircuitState.OPEN

    def test_threshold_1_opens_on_first_failure(self):
        cb = _cb(threshold=1)
        _fail(cb, 1)
        assert cb.state == CircuitState.OPEN

    def test_open_circuit_rejects_call_with_circuit_open_error(self):
        cb = _cb(threshold=3)
        _fail(cb, 3)
        with pytest.raises(CircuitOpenError):
            cb.call(_ok)

    def test_open_circuit_does_not_call_underlying_fn(self):
        cb = _cb(threshold=1)
        _fail(cb, 1)
        mock_fn = MagicMock(return_value="x")
        with pytest.raises(CircuitOpenError):
            cb.call(mock_fn)
        mock_fn.assert_not_called()

    def test_failure_count_continues_past_threshold(self):
        cb = _cb(threshold=2)
        _fail(cb, 2)
        assert cb.failure_count == 2


# ---------------------------------------------------------------------------
# OPEN → HALF_OPEN → CLOSED / OPEN
# ---------------------------------------------------------------------------


class TestHalfOpenTransition:
    def test_after_reset_timeout_state_becomes_half_open(self):
        cb = _cb(threshold=1, reset_timeout=0.01)
        _fail(cb, 1)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        cb = _cb(threshold=1, reset_timeout=0.01)
        _fail(cb, 1)
        time.sleep(0.02)
        cb.call(_ok)  # probe succeeds
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens_circuit(self):
        cb = _cb(threshold=1, reset_timeout=0.01)
        _fail(cb, 1)
        time.sleep(0.02)
        _fail(cb, 1)   # probe fails
        assert cb.state == CircuitState.OPEN

    def test_half_open_failure_restarts_timer(self):
        """After HALF_OPEN → OPEN, another wait should allow HALF_OPEN again."""
        cb = _cb(threshold=1, reset_timeout=0.01)
        _fail(cb, 1)
        time.sleep(0.02)
        _fail(cb, 1)   # back to OPEN
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# Manual reset
# ---------------------------------------------------------------------------


class TestManualReset:
    def test_reset_from_open_to_closed(self):
        cb = _cb(threshold=1)
        _fail(cb, 1)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_from_closed_is_noop(self):
        cb = _cb()
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_after_reset_calls_pass_through(self):
        cb = _cb(threshold=1)
        _fail(cb, 1)
        cb.reset()
        result = cb.call(lambda: 99)
        assert result == 99


# ---------------------------------------------------------------------------
# Thread-safety smoke test
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_concurrent_failures_do_not_corrupt_state(self):
        import threading

        cb = _cb(threshold=5)
        errors: list[Exception] = []

        def worker():
            try:
                _fail(cb, 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No uncaught exceptions and state is consistent
        assert cb.state in {CircuitState.CLOSED, CircuitState.OPEN}
        assert len(errors) == 0
