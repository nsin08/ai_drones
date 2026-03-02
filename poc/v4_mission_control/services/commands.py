"""Safe command path — W10 foundation + W12 retry loop and ACK/NACK."""

import threading
import time
from typing import Any
from uuid import UUID

from poc.src.ports.message_broker import MessageBroker

from ..config import Settings
from ..repos.command_repo import InMemoryCommandRepository, SQLCommandRepository, StoredCommand
from ..repos.event_repo import InMemoryEventRepository, SQLEventRepository
from ..schemas.command import (
    CommandAcceptedResponse,
    CommandHistoryItem,
    CommandRejectedResponse,
    CommandRequest,
    CommandStatus,
)
from ..schemas.preflight import PreflightResponse
from ..schemas.socket_events import COMMAND_STATUS_EVENT
from .preflight import PreflightService

# Terminal states — retry loop stops when a command reaches one of these.
_TERMINAL_STATUSES = {
    CommandStatus.ACKED,
    CommandStatus.FAILED,
    CommandStatus.REJECTED,
    CommandStatus.TIMED_OUT,
}


class CommandService:
    """Validate, persist, emit, retry, and ACK/NACK commands.

    W12 additions:
    - _retry_loop: background thread fires up to COMMAND_MAX_RETRIES times
    - ack_command / nack_command: callable from ACK/NACK REST endpoints
    """

    def __init__(
        self,
        *,
        settings: Settings,
        command_repo: InMemoryCommandRepository | SQLCommandRepository,
        event_repo: InMemoryEventRepository | SQLEventRepository,
        preflight_service: PreflightService,
        broker: MessageBroker | None = None,
    ) -> None:
        self._settings = settings
        self._command_repo = command_repo
        self._event_repo = event_repo
        self._preflight_service = preflight_service
        self._broker = broker

    def submit_command(
        self,
        request: CommandRequest,
        *,
        start_retry_thread: bool = True,
    ) -> CommandAcceptedResponse | CommandRejectedResponse:
        """Process one command request through the safe command path.

        If the command is accepted, a background thread is started to watch for
        ACK and retry up to COMMAND_MAX_RETRIES times on timeout.
        Set start_retry_thread=False in unit tests to avoid real sleep.
        """

        preflight = self._preflight_service.get_preflight(request.drone_id)
        rejection_reason = self._rejection_reason(request, preflight)
        if rejection_reason:
            record = self._command_repo.create(
                drone_id=request.drone_id,
                command=request.command,
                status=CommandStatus.REJECTED,
                params_json=request.params,
                requested_by=request.requested_by,
                client_request_id=request.client_request_id,
                preflight_snapshot_json=preflight.model_dump(mode="json"),
                rejection_reason=rejection_reason,
                mark_completed=True,
            )
            self._event_repo.append(
                event_type="COMMAND_REJECTED",
                aggregate_type="COMMAND",
                aggregate_id=str(record.cmd_id),
                drone_id=record.drone_id,
                command_id=record.cmd_id,
                severity="WARNING",
                payload_json={
                    "socket_event": COMMAND_STATUS_EVENT,
                    "status": record.status.value,
                    "rejection_reason": rejection_reason,
                    "attempt_count": record.attempt_count,
                },
                requested_by=record.requested_by,
            )
            return record.as_rejected_response()

        record = self._command_repo.create(
            drone_id=request.drone_id,
            command=request.command,
            status=CommandStatus.REQUESTED,
            params_json=request.params,
            requested_by=request.requested_by,
            client_request_id=request.client_request_id,
            preflight_snapshot_json=preflight.model_dump(mode="json"),
        )
        self._event_repo.append(
            event_type="COMMAND_REQUESTED",
            aggregate_type="COMMAND",
            aggregate_id=str(record.cmd_id),
            drone_id=record.drone_id,
            command_id=record.cmd_id,
            payload_json={
                "socket_event": COMMAND_STATUS_EVENT,
                "status": record.status.value,
                "attempt_count": record.attempt_count,
            },
            requested_by=record.requested_by,
        )
        self._publish_hook(record)

        if start_retry_thread:
            t = threading.Thread(
                target=self._retry_loop,
                args=(record.cmd_id,),
                daemon=True,
                name=f"retry-{record.cmd_id}",
            )
            t.start()

        return record.as_accepted_response()

    # ------------------------------------------------------------------
    # Retry loop (W12)
    # ------------------------------------------------------------------

    def _retry_loop(self, cmd_id: UUID) -> None:
        """Background thread: wait for ACK, retry on timeout, mark TIMED_OUT.

        Flow:
        1. Wait COMMAND_ACK_TIMEOUT_SEC for an ACK.
        2. If ACKed (or terminal), stop.
        3. Otherwise increment attempt, mark RETRYING, emit event, sleep backoff.
        4. After COMMAND_MAX_RETRIES exhausted, mark TIMED_OUT, emit event.
        """
        ack_timeout = self._settings.COMMAND_ACK_TIMEOUT_SEC
        backoffs = self._settings.COMMAND_RETRY_BACKOFF_SEC
        max_retries = self._settings.COMMAND_MAX_RETRIES

        for attempt in range(1, max_retries + 1):
            # Wait for ACK
            time.sleep(ack_timeout)

            current = self._command_repo.get(cmd_id)
            if current is None or current.status in _TERMINAL_STATUSES:
                return  # ACKed, failed, or externally resolved

            # Not ACKed — mark retrying and emit event
            self._command_repo.mark_retrying(cmd_id, attempt=attempt)
            self._event_repo.append(
                event_type="COMMAND_RETRYING",
                aggregate_type="COMMAND",
                aggregate_id=str(cmd_id),
                drone_id=current.drone_id,
                command_id=cmd_id,
                payload_json={
                    "socket_event": COMMAND_STATUS_EVENT,
                    "status": CommandStatus.RETRYING.value,
                    "attempt": attempt,
                },
                requested_by=current.requested_by,
            )

            # Sleep backoff before next attempt
            if attempt <= len(backoffs):
                time.sleep(backoffs[attempt - 1])

        # All retries exhausted — mark TIMED_OUT
        current = self._command_repo.get(cmd_id)
        if current and current.status not in _TERMINAL_STATUSES:
            self._command_repo.mark_timed_out(cmd_id)
            self._event_repo.append(
                event_type="COMMAND_TIMED_OUT",
                aggregate_type="COMMAND",
                aggregate_id=str(cmd_id),
                drone_id=current.drone_id,
                command_id=cmd_id,
                severity="WARNING",
                payload_json={
                    "socket_event": COMMAND_STATUS_EVENT,
                    "status": CommandStatus.TIMED_OUT.value,
                    "attempts_made": max_retries,
                },
                requested_by=current.requested_by,
            )

    # ------------------------------------------------------------------
    # ACK / NACK (W12)
    # ------------------------------------------------------------------

    def ack_command(self, cmd_id: UUID) -> CommandHistoryItem | None:
        """Mark a command as ACKed and emit a COMMAND_ACKED event.

        Called from POST /api/commands/{cmd_id}/ack.
        Returns the updated history item, or None if not found.
        """
        record = self._command_repo.get(cmd_id)
        if record is None:
            return None
        if record.status in _TERMINAL_STATUSES:
            # Idempotent — already in a final state, just return current state
            return record.as_history_item()

        self._command_repo.mark_acked(cmd_id)
        updated = self._command_repo.get(cmd_id)
        self._event_repo.append(
            event_type="COMMAND_ACKED",
            aggregate_type="COMMAND",
            aggregate_id=str(cmd_id),
            drone_id=record.drone_id,
            command_id=cmd_id,
            payload_json={
                "socket_event": COMMAND_STATUS_EVENT,
                "status": CommandStatus.ACKED.value,
                "attempt_count": record.attempt_count,
            },
            requested_by=record.requested_by,
        )
        return updated.as_history_item() if updated else None

    def nack_command(self, cmd_id: UUID, *, reason: str | None = None) -> CommandHistoryItem | None:
        """Mark a command as FAILED (NACK) and emit a COMMAND_FAILED event.

        Called from POST /api/commands/{cmd_id}/nack.
        """
        record = self._command_repo.get(cmd_id)
        if record is None:
            return None
        if record.status in _TERMINAL_STATUSES:
            return record.as_history_item()

        self._command_repo.mark_failed(cmd_id, reason=reason)
        updated = self._command_repo.get(cmd_id)
        self._event_repo.append(
            event_type="COMMAND_FAILED",
            aggregate_type="COMMAND",
            aggregate_id=str(cmd_id),
            drone_id=record.drone_id,
            command_id=cmd_id,
            severity="ERROR",
            payload_json={
                "socket_event": COMMAND_STATUS_EVENT,
                "status": CommandStatus.FAILED.value,
                "reason": reason or "nack",
            },
            requested_by=record.requested_by,
        )
        return updated.as_history_item() if updated else None

    def _rejection_reason(
        self,
        request: CommandRequest,
        preflight: PreflightResponse,
    ) -> str | None:
        if request.command != "ARM":
            return None
        reasons = self._preflight_service.arm_rejection_reasons(preflight)
        if not reasons:
            return None
        return "; ".join(reasons)

    def _publish_hook(self, record: StoredCommand) -> None:
        payload = {
            "cmd_id": str(record.cmd_id),
            "drone_id": record.drone_id,
            "command": record.command,
            "params": record.params_json,
            "ack_timeout_sec": self._settings.COMMAND_ACK_TIMEOUT_SEC,
            "max_retries": self._settings.COMMAND_MAX_RETRIES,
        }
        if self._broker:
            self._broker.publish(self._command_topic(record.drone_id), payload)
            event_type = "COMMAND_PUBLISH_REQUESTED"
            publish_mode = "broker"
        else:
            event_type = "COMMAND_PUBLISH_DEFERRED"
            publish_mode = "noop"

        self._event_repo.append(
            event_type=event_type,
            aggregate_type="COMMAND",
            aggregate_id=str(record.cmd_id),
            drone_id=record.drone_id,
            command_id=record.cmd_id,
            payload_json={
                "socket_event": COMMAND_STATUS_EVENT,
                "publish_mode": publish_mode,
                "topic": self._command_topic(record.drone_id),
            },
            requested_by=record.requested_by,
        )

    @staticmethod
    def _command_topic(drone_id: str) -> str:
        return f"fleet/{drone_id}/command"
