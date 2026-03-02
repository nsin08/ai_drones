"""Mission and Task ORM models for Mission Control v4."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, JsonBType, utc_now


class Mission(TimestampMixin, Base):
    """Represents a top-level fleet mission with one or more tasks.

    FSM states: IDLE → PLANNING → PLANNED → ACTIVE ↔ PAUSED → COMPLETED | ABORTED
    """

    __tablename__ = "missions"

    mission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="IDLE", index=True
    )
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JsonBType, default=dict, nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="mission", cascade="all, delete-orphan"
    )


class Task(TimestampMixin, Base):
    """A sub-unit of a Mission assigned to one or more drones.

    FSM states: PLANNED → ACTIVE → COMPLETED | FAILED | ABORTED
    """

    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("missions.mission_id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="PLANNED", index=True
    )
    drone_ids_json: Mapped[list[str]] = mapped_column(
        JsonBType, default=list, nullable=False
    )
    waypoints_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonBType, default=list, nullable=False
    )
    formation: Mapped[str | None] = mapped_column(String(16))

    mission: Mapped["Mission"] = relationship("Mission", back_populates="tasks")
