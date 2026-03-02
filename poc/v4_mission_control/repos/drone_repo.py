"""Drone and DroneSnapshot repositories for Mission Control v4."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class DroneRepository:
    """Manages drone registry rows in PostgreSQL."""

    def __init__(self, session_factory=None) -> None:
        if session_factory is not None:
            self._factory = session_factory
        else:
            from ..db.session import get_session_factory
            self._factory = get_session_factory()

    def upsert(
        self,
        *,
        drone_id: str,
        env: str = "SIM",
        last_seen_at: datetime | None = None,
        last_telemetry_json: dict[str, Any] | None = None,
        health_score: float | None = None,
        health_label: str | None = None,
    ) -> None:
        """Insert or update a drone registry row."""
        from ..models.drone import Drone

        session = self._factory()
        try:
            row = session.get(Drone, drone_id)
            if row is None:
                row = Drone(drone_id=drone_id, env=env)
                session.add(row)
            if last_seen_at is not None:
                row.last_seen_at = last_seen_at
            if last_telemetry_json is not None:
                row.last_telemetry_json = last_telemetry_json
            if health_score is not None:
                row.health_score = health_score
            if health_label is not None:
                row.health_label = health_label
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, drone_id: str) -> Any | None:
        """Return the Drone ORM row or None."""
        from ..models.drone import Drone

        session = self._factory()
        try:
            return session.get(Drone, drone_id)
        finally:
            session.close()

    def list_all(self, *, env: str | None = None) -> list[Any]:
        """List all registered drones, optionally filtered by env."""
        from ..models.drone import Drone

        session = self._factory()
        try:
            query = session.query(Drone)
            if env:
                query = query.filter(Drone.env == env.upper())
            return query.order_by(Drone.drone_id).all()
        finally:
            session.close()


class DroneSnapshotRepository:
    """Manages DroneSnapshot rows for event-replay optimisation."""

    def __init__(self, session_factory=None) -> None:
        if session_factory is not None:
            self._factory = session_factory
        else:
            from ..db.session import get_session_factory
            self._factory = get_session_factory()

    def latest(self, drone_id: str) -> Any | None:
        """Return the most recent DroneSnapshot for a drone, or None."""
        from ..models.drone import DroneSnapshot

        session = self._factory()
        try:
            return (
                session.query(DroneSnapshot)
                .filter(DroneSnapshot.drone_id == drone_id)
                .order_by(DroneSnapshot.version_seq.desc())
                .first()
            )
        finally:
            session.close()

    def write(
        self,
        *,
        drone_id: str,
        version_seq: int,
        state_json: dict[str, Any],
    ) -> None:
        """Persist a new snapshot for a drone."""
        from ..models.drone import DroneSnapshot

        snapshot = DroneSnapshot(
            drone_id=drone_id,
            version_seq=version_seq,
            state_json=state_json,
        )
        session = self._factory()
        try:
            session.add(snapshot)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# ---------------------------------------------------------------------------
# In-memory implementations (used when USE_DATABASE=False, i.e. unit tests)
# ---------------------------------------------------------------------------


@dataclass
class _InMemDrone:
    """Lightweight in-memory drone record matching the ORM Drone interface."""

    drone_id: str
    env: str = "SIM"
    last_seen_at: datetime | None = None
    last_telemetry_json: dict[str, Any] = field(default_factory=dict)
    health_score: float | None = None
    health_label: str | None = None


class InMemoryDroneRepository:
    """In-memory drone repository for unit tests (``USE_DATABASE=False``).

    Exposes the same public interface as :class:`DroneRepository` so that
    :class:`~poc.v4_mission_control.services.health_service.HealthService`
    and the service container are repository-agnostic.
    """

    def __init__(self) -> None:
        self._store: dict[str, _InMemDrone] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert(
        self,
        *,
        drone_id: str,
        env: str = "SIM",
        last_seen_at: datetime | None = None,
        last_telemetry_json: dict[str, Any] | None = None,
        health_score: float | None = None,
        health_label: str | None = None,
    ) -> None:
        """Insert or update an in-memory drone record."""
        if drone_id not in self._store:
            self._store[drone_id] = _InMemDrone(drone_id=drone_id, env=env)
        d = self._store[drone_id]
        if last_seen_at is not None:
            d.last_seen_at = last_seen_at
        if last_telemetry_json is not None:
            d.last_telemetry_json = last_telemetry_json
        if health_score is not None:
            d.health_score = health_score
        if health_label is not None:
            d.health_label = health_label

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, drone_id: str) -> _InMemDrone | None:
        """Return the in-memory drone record or None."""
        return self._store.get(drone_id)

    def list_all(self, *, env: str | None = None) -> list[_InMemDrone]:
        """List all drones, optionally filtered by env."""
        items: list[_InMemDrone] = list(self._store.values())
        if env:
            items = [d for d in items if d.env == env.upper()]
        return sorted(items, key=lambda d: d.drone_id)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all records (called from test fixtures)."""
        self._store.clear()
