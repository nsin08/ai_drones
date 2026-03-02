"""Shared SQLAlchemy base classes."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Cross-dialect JSON type: JSONB on PostgreSQL, plain JSON on SQLite (used in tests).
JsonBType = JSON().with_variant(JSONB(), "postgresql")

# Cross-dialect UUID type: native UUID on PostgreSQL, VARCHAR on SQLite.
UuidType = Uuid(as_uuid=True)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for v4 persistence models."""


class TimestampMixin:
    """Common created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
