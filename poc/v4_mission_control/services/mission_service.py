"""Mission Service — FSM-guarded mission lifecycle for v4 (W12).

Valid transitions:
    PLANNING  → PLANNED, ABORTED
    PLANNED   → ACTIVE, ABORTED
    ACTIVE    → PAUSED, COMPLETED, ABORTED
    PAUSED    → ACTIVE, ABORTED

All transitions emit domain events to the event repository.
"""

from typing import Any

from ..repos.event_repo import InMemoryEventRepository, SQLEventRepository
from ..repos.mission_repo import (
    InMemoryMissionRepository,
    SQLMissionRepository,
    StoredMission,
    StoredTask,
)
from ..schemas.mission import MissionCreateRequest, MissionResponse, MissionStatus, TaskResponse, TaskState


# ---------------------------------------------------------------------------
# FSM guard table
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.PLANNING: {MissionStatus.PLANNED, MissionStatus.ABORTED},
    MissionStatus.PLANNED: {MissionStatus.ACTIVE, MissionStatus.ABORTED},
    MissionStatus.ACTIVE: {
        MissionStatus.PAUSED,
        MissionStatus.COMPLETED,
        MissionStatus.ABORTED,
    },
    MissionStatus.PAUSED: {MissionStatus.ACTIVE, MissionStatus.ABORTED},
    # Terminal states — no outbound transitions
    MissionStatus.COMPLETED: set(),
    MissionStatus.ABORTED: set(),
}

_TERMINAL_STATUSES = {MissionStatus.COMPLETED, MissionStatus.ABORTED}


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _task_response(t: StoredTask) -> TaskResponse:
    from datetime import timezone

    def _iso(dt: Any) -> str:
        if hasattr(dt, "isoformat"):
            return dt.isoformat().replace("+00:00", "Z")
        return str(dt)

    return TaskResponse(
        task_id=t.task_id,
        mission_id=t.mission_id,
        type=t.type,
        state=t.state,
        drone_ids=t.drone_ids,
        waypoints=t.waypoints,
        formation=t.formation,
        created_at=_iso(t.created_at),
        updated_at=_iso(t.updated_at),
    )


def _mission_response(m: StoredMission) -> MissionResponse:
    def _iso(dt: Any) -> str | None:
        if dt is None:
            return None
        if hasattr(dt, "isoformat"):
            return dt.isoformat().replace("+00:00", "Z")
        return str(dt)

    def _iso_req(dt: Any) -> str:
        return _iso(dt) or ""

    return MissionResponse(
        mission_id=m.mission_id,
        type=m.type,
        status=m.status,
        created_by=m.created_by,
        config=m.config,
        tasks=[_task_response(t) for t in m.tasks],
        created_at=_iso_req(m.created_at),
        updated_at=_iso_req(m.updated_at),
        started_at=_iso(m.started_at),
        completed_at=_iso(m.completed_at),
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MissionService:
    """Manages mission lifecycle with FSM validation and event emission."""

    def __init__(
        self,
        *,
        mission_repo: InMemoryMissionRepository | SQLMissionRepository,
        event_repo: InMemoryEventRepository | SQLEventRepository,
    ) -> None:
        self._repo = mission_repo
        self._event_repo = event_repo

    # --- queries --------------------------------------------------------------

    def get_mission(self, mission_id: str) -> MissionResponse | None:
        record = self._repo.get(mission_id)
        if record is None:
            return None
        return _mission_response(record)

    def list_missions(
        self, *, status: MissionStatus | None = None
    ) -> list[MissionResponse]:
        records = self._repo.list_all(status=status)
        return [_mission_response(r) for r in records]

    # --- create ---------------------------------------------------------------

    def create_mission(self, request: MissionCreateRequest) -> MissionResponse:
        """Create a new mission in PLANNING state and emit MISSION_CREATED."""
        tasks_spec = [t.model_dump() for t in request.tasks]
        record = self._repo.create(
            type=request.type,
            tasks_spec=tasks_spec,
            created_by=request.created_by,
            config=request.config,
        )
        self._event_repo.append(
            event_type="MISSION_CREATED",
            aggregate_type="MISSION",
            aggregate_id=record.mission_id,
            mission_id=record.mission_id,
            payload_json={
                "status": record.status.value,
                "type": record.type,
                "task_count": len(record.tasks),
            },
            requested_by=request.created_by,
        )
        return _mission_response(record)

    # --- FSM transitions ------------------------------------------------------

    def _transition(
        self,
        mission_id: str,
        target: MissionStatus,
        *,
        requested_by: str | None = None,
        reason: str | None = None,
    ) -> MissionResponse:
        """Apply a validated FSM transition and emit an event."""
        record = self._repo.get(mission_id)
        if record is None:
            raise KeyError(f"Mission {mission_id!r} not found")

        allowed = _VALID_TRANSITIONS.get(record.status, set())
        if target not in allowed:
            raise ValueError(
                f"Cannot transition mission {mission_id!r} from {record.status.value!r}"
                f" to {target.value!r}. Allowed: {[s.value for s in allowed]}"
            )

        updated = self._repo.update_status(mission_id, new_status=target)
        if updated is None:
            raise RuntimeError(f"update_status failed for mission {mission_id!r}")

        self._event_repo.append(
            event_type=f"MISSION_{target.value}",
            aggregate_type="MISSION",
            aggregate_id=mission_id,
            mission_id=mission_id,
            payload_json={
                "previous_status": record.status.value,
                "new_status": target.value,
                "reason": reason,
            },
            requested_by=requested_by,
        )
        return _mission_response(updated)

    def plan_mission(
        self, mission_id: str, *, requested_by: str | None = None
    ) -> MissionResponse:
        """Advance mission from PLANNING → PLANNED."""
        return self._transition(
            mission_id, MissionStatus.PLANNED, requested_by=requested_by
        )

    def start_mission(
        self, mission_id: str, *, requested_by: str | None = None
    ) -> MissionResponse:
        """Advance mission from PLANNED → ACTIVE."""
        return self._transition(
            mission_id, MissionStatus.ACTIVE, requested_by=requested_by
        )

    def pause_mission(
        self, mission_id: str, *, requested_by: str | None = None
    ) -> MissionResponse:
        """Transition ACTIVE → PAUSED."""
        return self._transition(
            mission_id, MissionStatus.PAUSED, requested_by=requested_by
        )

    def resume_mission(
        self, mission_id: str, *, requested_by: str | None = None
    ) -> MissionResponse:
        """Transition PAUSED → ACTIVE."""
        return self._transition(
            mission_id, MissionStatus.ACTIVE, requested_by=requested_by
        )

    def complete_mission(
        self, mission_id: str, *, requested_by: str | None = None
    ) -> MissionResponse:
        """Transition ACTIVE → COMPLETED."""
        return self._transition(
            mission_id, MissionStatus.COMPLETED, requested_by=requested_by
        )

    def abort_mission(
        self,
        mission_id: str,
        *,
        requested_by: str | None = None,
        reason: str | None = None,
    ) -> MissionResponse:
        """Abort a mission from any non-terminal state."""
        return self._transition(
            mission_id,
            MissionStatus.ABORTED,
            requested_by=requested_by,
            reason=reason,
        )

    # --- task helpers ---------------------------------------------------------

    def assign_drone(
        self, mission_id: str, task_id: str, drone_id: str
    ) -> TaskResponse | None:
        t = self._repo.assign_drone_to_task(mission_id, task_id, drone_id)
        return _task_response(t) if t else None

    def update_task_state(
        self,
        mission_id: str,
        task_id: str,
        *,
        new_state: TaskState,
        requested_by: str | None = None,
    ) -> TaskResponse | None:
        t = self._repo.update_task_state(mission_id, task_id, new_state=new_state)
        if t is None:
            return None
        self._event_repo.append(
            event_type=f"TASK_{new_state.value}",
            aggregate_type="TASK",
            aggregate_id=task_id,
            mission_id=mission_id,
            payload_json={"new_state": new_state.value},
            requested_by=requested_by,
        )
        return _task_response(t)
