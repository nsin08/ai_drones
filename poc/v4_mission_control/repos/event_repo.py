"""Temporary in-memory event repository."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class StoredEvent:
    """Stored event record mirroring the pinned W10 shape."""

    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    drone_id: str | None
    command_id: UUID | None
    mission_id: str | None
    severity: str | None
    payload_json: dict[str, Any]
    requested_by: str | None
    created_at: datetime


class InMemoryEventRepository:
    """Simple append-only event store for W10."""

    def __init__(self) -> None:
        self._events: list[StoredEvent] = []

    def append(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        drone_id: str | None = None,
        command_id: UUID | None = None,
        mission_id: str | None = None,
        severity: str | None = None,
        payload_json: dict[str, Any] | None = None,
        requested_by: str | None = None,
    ) -> StoredEvent:
        record = StoredEvent(
            event_id=uuid4(),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            drone_id=drone_id,
            command_id=command_id,
            mission_id=mission_id,
            severity=severity,
            payload_json=dict(payload_json or {}),
            requested_by=requested_by,
            created_at=_utc_now(),
        )
        self._events.append(record)
        return record

    def list_recent(self, *, limit: int = 50) -> list[StoredEvent]:
        return list(reversed(self._events[-limit:]))

    def clear(self) -> None:
        self._events.clear()
