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

    def get(self, cmd_id: UUID) -> StoredCommand | None:
        for record in self._commands:
            if record.cmd_id == cmd_id:
                return record
        return None

    def mark_retrying(self, cmd_id: UUID, *, attempt: int) -> None:
        record = self.get(cmd_id)
        if record:
            record.status = CommandStatus.RETRYING
            record.attempt_count = attempt
            record.last_attempt_at = _utc_now()
            record.updated_at = _utc_now()

    def mark_acked(self, cmd_id: UUID) -> None:
        record = self.get(cmd_id)
        if record:
            record.status = CommandStatus.ACKED
            record.completed_at = _utc_now()
            record.updated_at = _utc_now()

    def mark_timed_out(self, cmd_id: UUID) -> None:
        record = self.get(cmd_id)
        if record:
            record.status = CommandStatus.TIMED_OUT
            record.completed_at = _utc_now()
            record.updated_at = _utc_now()

    def mark_failed(self, cmd_id: UUID, *, reason: str | None = None) -> None:
        record = self.get(cmd_id)
        if record:
            record.status = CommandStatus.FAILED
            if reason:
                record.rejection_reason = reason
            record.completed_at = _utc_now()
            record.updated_at = _utc_now()

    def clear(self) -> None:
        self._commands.clear()


# ---------------------------------------------------------------------------
# SQL-backed repository
# ---------------------------------------------------------------------------

class SQLCommandRepository:
    """PostgreSQL-backed command repository using SQLAlchemy.

    Implements the same interface as InMemoryCommandRepository so the
    CommandService works unchanged regardless of which repo is injected.
    """

    def __init__(self, session_factory=None) -> None:
        if session_factory is not None:
            self._factory = session_factory
        else:
            from ..db.session import get_session_factory
            self._factory = get_session_factory()

    def _to_stored(self, row: Any) -> StoredCommand:
        """Convert an ORM Command row to a StoredCommand dataclass."""
        from ..models.command import Command  # local to avoid circular import

        return StoredCommand(
            cmd_id=row.cmd_id,
            drone_id=row.drone_id,
            command=row.command,
            status=CommandStatus(row.status),
            params_json=row.params_json or {},
            attempt_count=row.attempt_count,
            requested_by=row.requested_by,
            client_request_id=row.client_request_id,
            preflight_snapshot_json=row.preflight_snapshot_json,
            rejection_reason=row.rejection_reason,
            requested_at=row.requested_at,
            last_attempt_at=row.last_attempt_at,
            completed_at=row.completed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

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
        from ..models.command import Command

        now = _utc_now()
        row = Command(
            drone_id=drone_id,
            command=command,
            status=status.value,
            params_json=dict(params_json or {}),
            attempt_count=attempt_count,
            requested_by=requested_by,
            client_request_id=client_request_id,
            preflight_snapshot_json=dict(preflight_snapshot_json or {}) or None,
            rejection_reason=rejection_reason,
            requested_at=now,
            completed_at=now if mark_completed else None,
        )
        session = self._factory()
        try:
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_stored(row)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_recent(
        self,
        *,
        drone_id: str | None = None,
        limit: int = 20,
    ) -> list[StoredCommand]:
        from ..models.command import Command

        session = self._factory()
        try:
            query = session.query(Command).order_by(Command.created_at.desc())
            if drone_id:
                query = query.filter(Command.drone_id == drone_id)
            rows = query.limit(limit).all()
            return [self._to_stored(r) for r in rows]
        finally:
            session.close()

    def get(self, cmd_id: UUID) -> StoredCommand | None:
        from ..models.command import Command

        session = self._factory()
        try:
            row = session.query(Command).filter(Command.cmd_id == cmd_id).first()
            return self._to_stored(row) if row else None
        finally:
            session.close()

    def _update_status(self, cmd_id: UUID, **fields: Any) -> None:
        """Helper: update Command row fields atomically."""
        from ..models.command import Command
        from sqlalchemy import update

        session = self._factory()
        try:
            fields["updated_at"] = _utc_now()
            session.execute(
                update(Command)
                .where(Command.cmd_id == cmd_id)
                .values(**fields)
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def mark_retrying(self, cmd_id: UUID, *, attempt: int) -> None:
        self._update_status(
            cmd_id,
            status=CommandStatus.RETRYING.value,
            attempt_count=attempt,
            last_attempt_at=_utc_now(),
        )

    def mark_acked(self, cmd_id: UUID) -> None:
        self._update_status(
            cmd_id,
            status=CommandStatus.ACKED.value,
            completed_at=_utc_now(),
        )

    def mark_timed_out(self, cmd_id: UUID) -> None:
        self._update_status(
            cmd_id,
            status=CommandStatus.TIMED_OUT.value,
            completed_at=_utc_now(),
        )

    def mark_failed(self, cmd_id: UUID, *, reason: str | None = None) -> None:
        extra = {"rejection_reason": reason} if reason else {}
        self._update_status(
            cmd_id,
            status=CommandStatus.FAILED.value,
            completed_at=_utc_now(),
            **extra,
        )

    def clear(self) -> None:
        """Not supported for SQL repository — data is durable."""
        raise NotImplementedError("SQLCommandRepository does not support clear()")
