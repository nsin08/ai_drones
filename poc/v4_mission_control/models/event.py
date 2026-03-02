"""SQLAlchemy event model skeleton."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, JsonBType, UuidType, utc_now


class Event(Base):
    """Pinned W10 events table shape."""

    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UuidType,
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    drone_id: Mapped[str | None] = mapped_column(String(64), index=True)
    command_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType,
        ForeignKey("commands.cmd_id"),
    )
    mission_id: Mapped[str | None] = mapped_column(String(64), index=True)
    severity: Mapped[str | None] = mapped_column(String(16), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JsonBType, default=dict, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
