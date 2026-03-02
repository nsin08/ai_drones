"""Drone registry and snapshot ORM models for Mission Control v4."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, JsonBType, UuidType, utc_now


class Drone(TimestampMixin, Base):
    """Registered drone with last-known telemetry and health state.

    Populated on first telemetry receipt; updated on each ingest.
    """

    __tablename__ = "drones"

    drone_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    env: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SIM", index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_telemetry_json: Mapped[dict[str, Any]] = mapped_column(
        JsonBType, default=dict, nullable=False
    )
    health_score: Mapped[float | None] = mapped_column(Float)
    health_label: Mapped[str | None] = mapped_column(
        String(16), index=True
    )  # GREEN | YELLOW | RED | OFFLINE


class DroneSnapshot(Base):
    """Point-in-time snapshot of a drone's reconstructed state.

    Written every EVENT_SNAPSHOT_INTERVAL events per drone to bound
    the cost of state replay from the event log.
    """

    __tablename__ = "drone_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UuidType,
        primary_key=True,
        default=uuid.uuid4,
    )
    drone_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JsonBType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
