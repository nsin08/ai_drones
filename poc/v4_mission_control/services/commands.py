"""Safe command path skeleton for Mission Control v4."""

from poc.src.ports.message_broker import MessageBroker

from ..config import Settings
from ..repos.command_repo import InMemoryCommandRepository, StoredCommand
from ..repos.event_repo import InMemoryEventRepository
from ..schemas.command import (
    CommandAcceptedResponse,
    CommandRejectedResponse,
    CommandRequest,
    CommandStatus,
)
from ..schemas.preflight import PreflightResponse
from ..schemas.socket_events import COMMAND_STATUS_EVENT
from .preflight import PreflightService


class CommandService:
    """Validate, persist, emit, and hand off commands."""

    def __init__(
        self,
        *,
        settings: Settings,
        command_repo: InMemoryCommandRepository,
        event_repo: InMemoryEventRepository,
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
    ) -> CommandAcceptedResponse | CommandRejectedResponse:
        """Process one command request through the safe command path."""

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
        return record.as_accepted_response()

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
