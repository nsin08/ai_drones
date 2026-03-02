"""Temporary in-memory command repository.

This keeps the safe command path functional before the SQLAlchemy session layer
is wired to PostgreSQL.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from ..schemas.command import (
    CommandAcceptedResponse,
    CommandHistoryItem,
    CommandRejectedResponse,
    CommandStatus,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class StoredCommand:
    """Stored command record mirroring the pinned W10 shape."""

    cmd_id: UUID
    drone_id: str
    command: str
    status: CommandStatus
    params_json: dict[str, Any]
    attempt_count: int
    requested_by: str | None
    client_request_id: str | None
    preflight_snapshot_json: dict[str, Any] | None
    rejection_reason: str | None
    requested_at: datetime
    last_attempt_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def as_history_item(self) -> CommandHistoryItem:
        return CommandHistoryItem(
            cmd_id=self.cmd_id,
            drone_id=self.drone_id,
            command=self.command,
            status=self.status,
            attempt_count=self.attempt_count,
            created_at=_as_iso(self.created_at),
        )

    def as_accepted_response(self) -> CommandAcceptedResponse:
        return CommandAcceptedResponse(
            cmd_id=self.cmd_id,
            accepted=True,
            status=self.status,
            drone_id=self.drone_id,
            command=self.command,
            attempt_count=self.attempt_count,
            rejection_reason=None,
            created_at=_as_iso(self.created_at),
        )

    def as_rejected_response(self) -> CommandRejectedResponse:
        return CommandRejectedResponse(
            accepted=False,
            status=CommandStatus.REJECTED,
            drone_id=self.drone_id,
            command=self.command,
            rejection_reason=self.rejection_reason or "command rejected",
        )


class InMemoryCommandRepository:
    """Simple append/query repository for the v4 foundation slice."""

    def __init__(self) -> None:
        self._commands: list[StoredCommand] = []

    def create(
        self,
        *,
        drone_id: str,
        command: str,
        status: CommandStatus,
        params_json: dict[str, Any] | None = None,
        attempt_count: int = 0,
        requested_by: str | None = None,
        client_request_id: str | None = None,
        preflight_snapshot_json: dict[str, Any] | None = None,
        rejection_reason: str | None = None,
        mark_completed: bool = False,
    ) -> StoredCommand:
        now = _utc_now()
        completed_at = now if mark_completed else None
        record = StoredCommand(
            cmd_id=uuid4(),
            drone_id=drone_id,
            command=command,
            status=status,
            params_json=dict(params_json or {}),
            attempt_count=attempt_count,
            requested_by=requested_by,
            client_request_id=client_request_id,
            preflight_snapshot_json=dict(preflight_snapshot_json or {}) or None,
            rejection_reason=rejection_reason,
            requested_at=now,
            last_attempt_at=None,
            completed_at=completed_at,
            created_at=now,
            updated_at=now,
        )
        self._commands.append(record)
        return record

    def list_recent(
        self,
        *,
        drone_id: str | None = None,
        limit: int = 20,
    ) -> list[StoredCommand]:
        items = self._commands
        if drone_id:
            items = [item for item in items if item.drone_id == drone_id]
        return list(reversed(items[-limit:]))

    def clear(self) -> None:
        self._commands.clear()
