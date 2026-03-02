"""Mission and Task schemas for Mission Control v4 (W12)."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MissionStatus(str, Enum):
    """Mission lifecycle states.

    FSM:
        PLANNING ──► PLANNED ──► ACTIVE ◄──► PAUSED
                                   │
                              COMPLETED | ABORTED
    PLANNING may also go directly to ABORTED (cancel before planning complete).
    """

    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class TaskState(str, Enum):
    """Task lifecycle states.

    FSM: PLANNED ──► ACTIVE ──► COMPLETED | FAILED | ABORTED
    """

    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TaskCreateRequest(BaseModel):
    """Spec for one task within a new mission."""

    type: str
    drone_ids: list[str] = Field(default_factory=list)
    waypoints: list[dict[str, Any]] = Field(default_factory=list)
    formation: str | None = None


class MissionCreateRequest(BaseModel):
    """Create a new mission in PLANNING state."""

    type: str
    tasks: list[TaskCreateRequest] = Field(default_factory=list)
    created_by: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class MissionTransitionRequest(BaseModel):
    """Request a mission state transition."""

    requested_by: str | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TaskResponse(BaseModel):
    """One task within a mission response."""

    task_id: str
    mission_id: str
    type: str
    state: TaskState
    drone_ids: list[str]
    waypoints: list[dict[str, Any]]
    formation: str | None
    created_at: str
    updated_at: str


class MissionResponse(BaseModel):
    """Full mission detail."""

    mission_id: str
    type: str
    status: MissionStatus
    created_by: str | None
    config: dict[str, Any]
    tasks: list[TaskResponse]
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class MissionListResponse(BaseModel):
    """Paginated mission list."""

    items: list[MissionResponse]
    total: int
