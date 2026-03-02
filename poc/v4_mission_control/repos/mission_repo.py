"""Mission + Task repositories for Mission Control v4 (W12).

Provides both an in-memory implementation (used by tests without a database)
and a SQL-backed implementation using the Mission / Task ORM models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..schemas.mission import MissionStatus, TaskState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace("+00:00", "Z")


def _iso_req(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# In-memory data structures
# ---------------------------------------------------------------------------


@dataclass
class StoredTask:
    task_id: str
    mission_id: str
    type: str
    state: TaskState
    drone_ids: list[str]
    waypoints: list[dict[str, Any]]
    formation: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class StoredMission:
    mission_id: str
    type: str
    status: MissionStatus
    created_by: str | None
    config: dict[str, Any]
    tasks: list[StoredTask]
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# In-memory repository
# ---------------------------------------------------------------------------


class InMemoryMissionRepository:
    """Thread-unsafe in-memory mission store for unit tests."""

    def __init__(self) -> None:
        self._missions: dict[str, StoredMission] = {}

    # --- read -----------------------------------------------------------------

    def get(self, mission_id: str) -> StoredMission | None:
        return self._missions.get(mission_id)

    def list_all(self, *, status: MissionStatus | None = None) -> list[StoredMission]:
        missions = list(self._missions.values())
        if status is not None:
            missions = [m for m in missions if m.status == status]
        return sorted(missions, key=lambda m: m.created_at, reverse=True)

    # --- write ----------------------------------------------------------------

    def create(
        self,
        *,
        type: str,
        tasks_spec: list[dict[str, Any]],
        created_by: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> StoredMission:
        now = _utc_now()
        mission_id = str(uuid4())
        tasks = [
            StoredTask(
                task_id=str(uuid4()),
                mission_id=mission_id,
                type=t.get("type", "GENERIC"),
                state=TaskState.PLANNED,
                drone_ids=list(t.get("drone_ids", [])),
                waypoints=list(t.get("waypoints", [])),
                formation=t.get("formation"),
                created_at=now,
                updated_at=now,
            )
            for t in tasks_spec
        ]
        record = StoredMission(
            mission_id=mission_id,
            type=type,
            status=MissionStatus.PLANNING,
            created_by=created_by,
            config=dict(config or {}),
            tasks=tasks,
            created_at=now,
            updated_at=now,
        )
        self._missions[mission_id] = record
        return record

    def update_status(
        self,
        mission_id: str,
        *,
        new_status: MissionStatus,
    ) -> StoredMission | None:
        record = self._missions.get(mission_id)
        if record is None:
            return None
        now = _utc_now()
        record.status = new_status
        record.updated_at = now
        if new_status == MissionStatus.ACTIVE and record.started_at is None:
            record.started_at = now
        if new_status in (MissionStatus.COMPLETED, MissionStatus.ABORTED):
            record.completed_at = now
        return record

    def assign_drone_to_task(
        self,
        mission_id: str,
        task_id: str,
        drone_id: str,
    ) -> StoredTask | None:
        record = self._missions.get(mission_id)
        if record is None:
            return None
        for task in record.tasks:
            if task.task_id == task_id:
                if drone_id not in task.drone_ids:
                    task.drone_ids.append(drone_id)
                task.updated_at = _utc_now()
                return task
        return None

    def update_task_state(
        self,
        mission_id: str,
        task_id: str,
        *,
        new_state: TaskState,
    ) -> StoredTask | None:
        record = self._missions.get(mission_id)
        if record is None:
            return None
        for task in record.tasks:
            if task.task_id == task_id:
                task.state = new_state
                task.updated_at = _utc_now()
                return task
        return None

    def clear(self) -> None:
        self._missions.clear()


# ---------------------------------------------------------------------------
# SQL-backed repository
# ---------------------------------------------------------------------------


class SQLMissionRepository:
    """PostgreSQL-backed mission repository using the Mission/Task ORM models.

    Uses a single SQLAlchemy session per call (same pattern as SQLCommandRepository).
    """

    def get(self, mission_id: str) -> StoredMission | None:
        from ..db.session import get_session
        from ..models.mission import Mission, Task

        with get_session() as db:
            row = db.get(Mission, mission_id)
            if row is None:
                return None
            return self._to_stored(row)

    def list_all(self, *, status: MissionStatus | None = None) -> list[StoredMission]:
        from sqlalchemy import select

        from ..db.session import get_session
        from ..models.mission import Mission

        with get_session() as db:
            stmt = select(Mission).order_by(Mission.created_at.desc())
            if status is not None:
                stmt = stmt.where(Mission.status == status.value)
            rows = db.scalars(stmt).all()
            return [self._to_stored(r) for r in rows]

    def create(
        self,
        *,
        type: str,
        tasks_spec: list[dict[str, Any]],
        created_by: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> StoredMission:
        from ..db.session import get_session
        from ..models.mission import Mission, Task

        mission_id = str(uuid4())
        now = _utc_now()
        with get_session() as db:
            row = Mission(
                mission_id=mission_id,
                type=type,
                status=MissionStatus.PLANNING.value,
                created_by=created_by,
                config_json=dict(config or {}),
            )
            db.add(row)
            for t in tasks_spec:
                db.add(
                    Task(
                        task_id=str(uuid4()),
                        mission_id=mission_id,
                        type=t.get("type", "GENERIC"),
                        state=TaskState.PLANNED.value,
                        drone_ids_json=list(t.get("drone_ids", [])),
                        waypoints_json=list(t.get("waypoints", [])),
                        formation=t.get("formation"),
                    )
                )
            db.flush()
            result = self._to_stored(row)
        return result

    def update_status(
        self,
        mission_id: str,
        *,
        new_status: MissionStatus,
    ) -> StoredMission | None:
        from sqlalchemy import update

        from ..db.session import get_session
        from ..models.mission import Mission

        now = _utc_now()
        extra: dict[str, Any] = {}
        if new_status == MissionStatus.ACTIVE:
            # Only set started_at on first ACTIVE transition — handled in service
            extra["started_at"] = now
        if new_status in (MissionStatus.COMPLETED, MissionStatus.ABORTED):
            extra["completed_at"] = now

        with get_session() as db:
            db.execute(
                update(Mission)
                .where(Mission.mission_id == mission_id)
                .values(status=new_status.value, updated_at=now, **extra)
            )
            row = db.get(Mission, mission_id)
            if row is None:
                return None
            return self._to_stored(row)

    def assign_drone_to_task(
        self,
        mission_id: str,
        task_id: str,
        drone_id: str,
    ) -> StoredTask | None:
        from sqlalchemy import update

        from ..db.session import get_session
        from ..models.mission import Task

        with get_session() as db:
            task_row = db.get(Task, task_id)
            if task_row is None or task_row.mission_id != mission_id:
                return None
            ids = list(task_row.drone_ids_json or [])
            if drone_id not in ids:
                ids.append(drone_id)
            db.execute(
                update(Task)
                .where(Task.task_id == task_id)
                .values(drone_ids_json=ids, updated_at=_utc_now())
            )
            db.refresh(task_row)
            return self._task_to_stored(task_row)

    def update_task_state(
        self,
        mission_id: str,
        task_id: str,
        *,
        new_state: TaskState,
    ) -> StoredTask | None:
        from sqlalchemy import update

        from ..db.session import get_session
        from ..models.mission import Task

        with get_session() as db:
            task_row = db.get(Task, task_id)
            if task_row is None or task_row.mission_id != mission_id:
                return None
            db.execute(
                update(Task)
                .where(Task.task_id == task_id)
                .values(state=new_state.value, updated_at=_utc_now())
            )
            db.refresh(task_row)
            return self._task_to_stored(task_row)

    # --- helpers -------------------------------------------------------------

    def _task_to_stored(self, row: Any) -> StoredTask:
        return StoredTask(
            task_id=row.task_id,
            mission_id=row.mission_id,
            type=row.type,
            state=TaskState(row.state),
            drone_ids=list(row.drone_ids_json or []),
            waypoints=list(row.waypoints_json or []),
            formation=row.formation,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_stored(self, row: Any) -> StoredMission:
        return StoredMission(
            mission_id=row.mission_id,
            type=row.type,
            status=MissionStatus(row.status),
            created_by=row.created_by,
            config=dict(row.config_json or {}),
            tasks=[self._task_to_stored(t) for t in (row.tasks or [])],
            created_at=row.created_at,
            updated_at=row.updated_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
