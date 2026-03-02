"""Unit tests: Command retry loop, ACK, and NACK — W12.

All tests run with start_retry_thread=False so there is no real
time.sleep() involved; the retry loop logic is tested by calling
_retry_loop() directly or by verifying repo state after manual transitions.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest

from poc.v4_mission_control.repos.command_repo import InMemoryCommandRepository
from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository
from poc.v4_mission_control.schemas.command import CommandRequest, CommandStatus
from poc.v4_mission_control.services.commands import CommandService
from poc.v4_mission_control.services.preflight import PreflightService
from poc.v4_mission_control.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    defaults = {
        "SERVICE_NAME": "test",
        "ENVIRONMENT": "SIM",
        "USE_DATABASE": False,
        "COMMAND_MAX_RETRIES": 3,
        "COMMAND_RETRY_BACKOFF_SEC": (0, 0, 0),   # zero sleep for tests
        "COMMAND_ACK_TIMEOUT_SEC": 0,              # zero sleep for tests
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_service(
    settings: Settings | None = None,
) -> tuple[CommandService, InMemoryCommandRepository, InMemoryEventRepository]:
    s = settings or _settings()
    command_repo = InMemoryCommandRepository()
    event_repo = InMemoryEventRepository()
    preflight_service = PreflightService(settings=s)
    svc = CommandService(
        settings=s,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
    )
    return svc, command_repo, event_repo


def _good_request(drone_id: str = "SIM-001") -> CommandRequest:
    return CommandRequest(drone_id=drone_id, command="TAKEOFF", params={"alt_m": 10})


# ---------------------------------------------------------------------------
# submit_command tests
# ---------------------------------------------------------------------------


class TestSubmitCommand:
    def test_accepted_command_is_in_requested_state(self):
        svc, repo, _ = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        assert result.status == CommandStatus.REQUESTED

    def test_rejected_command_not_stored_as_requested(self):
        svc, repo, _ = _make_service()
        req = CommandRequest(drone_id="HW-LOWBAT-UNCAL-001", command="ARM")
        result = svc.submit_command(req, start_retry_thread=False)
        assert result.status == CommandStatus.REJECTED  # type: ignore[union-attr]

    def test_accepted_command_emits_command_requested_event(self):
        svc, repo, event_repo = _make_service()
        svc.submit_command(_good_request(), start_retry_thread=False)
        types = [e.event_type for e in event_repo._events]
        assert "COMMAND_REQUESTED" in types

    def test_rejected_command_emits_command_rejected_event(self):
        svc, repo, event_repo = _make_service()
        req = CommandRequest(drone_id="HW-LOWBAT-UNCAL-001", command="ARM")
        svc.submit_command(req, start_retry_thread=False)
        types = [e.event_type for e in event_repo._events]
        assert "COMMAND_REJECTED" in types


# ---------------------------------------------------------------------------
# Retry loop tests
# ---------------------------------------------------------------------------


class TestRetryLoop:
    def test_retry_loop_marks_timed_out_when_no_ack(self):
        """_retry_loop marks TIMED_OUT after all retries yield no ACK."""
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]

        # Run the retry loop synchronously (ACK_TIMEOUT=0, backoff=(0,0,0))
        svc._retry_loop(cmd_id)

        record = repo.get(cmd_id)
        assert record is not None
        assert record.status == CommandStatus.TIMED_OUT

    def test_retry_loop_emits_retrying_events(self):
        """_retry_loop emits COMMAND_RETRYING for each attempt."""
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]
        event_repo.clear()  # reset so we only count retry events

        svc._retry_loop(cmd_id)

        retry_events = [e for e in event_repo._events if e.event_type == "COMMAND_RETRYING"]
        assert len(retry_events) == 3  # COMMAND_MAX_RETRIES = 3

    def test_retry_loop_emits_timed_out_event(self):
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]

        svc._retry_loop(cmd_id)

        types = [e.event_type for e in event_repo._events]
        assert "COMMAND_TIMED_OUT" in types

    def test_retry_loop_stops_early_when_acked(self):
        """If ACK arrives before retry loop finishes, loop stops without TIMED_OUT."""
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]

        # ACK before retry loop runs
        repo.mark_acked(cmd_id)
        event_repo.clear()

        svc._retry_loop(cmd_id)

        record = repo.get(cmd_id)
        assert record.status == CommandStatus.ACKED
        assert not any(e.event_type == "COMMAND_TIMED_OUT" for e in event_repo._events)

    def test_retry_loop_stops_early_when_rejected(self):
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]

        repo.mark_failed(cmd_id, reason="operator nack")
        event_repo.clear()

        svc._retry_loop(cmd_id)

        record = repo.get(cmd_id)
        assert record.status == CommandStatus.FAILED
        assert not any(e.event_type == "COMMAND_TIMED_OUT" for e in event_repo._events)


# ---------------------------------------------------------------------------
# ACK / NACK tests
# ---------------------------------------------------------------------------


class TestAckNack:
    def test_ack_command_marks_acked(self):
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]

        acked = svc.ack_command(cmd_id)

        assert acked is not None
        assert acked.status == CommandStatus.ACKED

    def test_ack_command_emits_acked_event(self):
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]
        event_repo.clear()

        svc.ack_command(cmd_id)

        types = [e.event_type for e in event_repo._events]
        assert "COMMAND_ACKED" in types

    def test_ack_nonexistent_returns_none(self):
        svc, _, _ = _make_service()
        assert svc.ack_command(uuid4()) is None

    def test_nack_command_marks_failed(self):
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]

        nacked = svc.nack_command(cmd_id, reason="drone offline")

        assert nacked is not None
        assert nacked.status == CommandStatus.FAILED

    def test_nack_command_emits_failed_event(self):
        svc, repo, event_repo = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]
        event_repo.clear()

        svc.nack_command(cmd_id, reason="drone offline")

        types = [e.event_type for e in event_repo._events]
        assert "COMMAND_FAILED" in types

    def test_ack_is_idempotent_when_already_acked(self):
        """ACKing an already-ACKed command returns current state without erroring."""
        svc, repo, _ = _make_service()
        result = svc.submit_command(_good_request(), start_retry_thread=False)
        cmd_id = result.cmd_id  # type: ignore[union-attr]

        svc.ack_command(cmd_id)
        # Second ACK should be no-op
        second = svc.ack_command(cmd_id)
        assert second is not None
        assert second.status == CommandStatus.ACKED
