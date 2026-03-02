"""SQLAlchemy command model skeleton."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, JsonBType, UuidType, utc_now


class Command(TimestampMixin, Base):
    """Pinned W10 commands table shape."""

    __tablename__ = "commands"

    cmd_id: Mapped[uuid.UUID] = mapped_column(
        UuidType,
        primary_key=True,
        default=uuid.uuid4,
    )
    drone_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    params_json: Mapped[dict[str, Any]] = mapped_column(JsonBType, default=dict, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(64))
    client_request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    preflight_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JsonBType)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
