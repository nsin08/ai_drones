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


# ---------------------------------------------------------------------------
# SQL-backed repository
# ---------------------------------------------------------------------------

class SQLEventRepository:
    """PostgreSQL-backed append-only event repository.

    Triggers a DroneSnapshot every EVENT_SNAPSHOT_INTERVAL events per
    drone_id to keep state-replay cost bounded.
    """

    def __init__(self, session_factory=None) -> None:
        if session_factory is not None:
            self._factory = session_factory
        else:
            from ..db.session import get_session_factory
            self._factory = get_session_factory()

        from ..config import get_settings
        self._snapshot_interval: int = get_settings().EVENT_SNAPSHOT_INTERVAL

    def _to_stored(self, row: Any) -> StoredEvent:
        from ..models.event import Event

        return StoredEvent(
            event_id=row.event_id,
            event_type=row.event_type,
            aggregate_type=row.aggregate_type,
            aggregate_id=row.aggregate_id,
            drone_id=row.drone_id,
            command_id=row.command_id,
            mission_id=row.mission_id,
            severity=row.severity,
            payload_json=row.payload_json or {},
            requested_by=row.requested_by,
            created_at=row.created_at,
        )

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
        from ..models.event import Event

        row = Event(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            drone_id=drone_id,
            command_id=command_id,
            mission_id=mission_id,
            severity=severity,
            payload_json=dict(payload_json or {}),
            requested_by=requested_by,
        )
        session = self._factory()
        try:
            session.add(row)
            session.flush()  # get event_id before snapshot check
            stored = self._to_stored(row)
            self._maybe_snapshot(session, drone_id)
            session.commit()
            return stored
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _maybe_snapshot(self, session: Any, drone_id: str | None) -> None:
        """Write a DroneSnapshot if drone event count hits the interval threshold."""
        if not drone_id:
            return

        from ..models.event import Event
        from ..models.drone import DroneSnapshot

        count = (
            session.query(Event)
            .filter(Event.drone_id == drone_id)
            .count()
        )
        if count % self._snapshot_interval == 0:
            latest_telemetry = (
                session.query(Event)
                .filter(Event.drone_id == drone_id)
                .order_by(Event.created_at.desc())
                .first()
            )
            snapshot = DroneSnapshot(
                drone_id=drone_id,
                version_seq=count,
                state_json=latest_telemetry.payload_json if latest_telemetry else {},
            )
            session.add(snapshot)

    def list_recent(self, *, drone_id: str | None = None, limit: int = 50) -> list[StoredEvent]:
        from ..models.event import Event

        session = self._factory()
        try:
            query = session.query(Event).order_by(Event.created_at.desc())
            if drone_id:
                query = query.filter(Event.drone_id == drone_id)
            rows = query.limit(limit).all()
            return [self._to_stored(r) for r in rows]
        finally:
            session.close()

    def clear(self) -> None:
        """Not supported — event log is append-only and immutable."""
        raise NotImplementedError("SQLEventRepository is append-only; clear() is not permitted")
