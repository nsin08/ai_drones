"""Operator ORM model for Mission Control v4."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Operator(TimestampMixin, Base):
    """Registered operator with role-based access level.

    Roles:
      OBSERVER  — read-only (GET endpoints only)
      PILOT     — read + submit commands for assigned drones
      ADMIN     — unrestricted
    """

    __tablename__ = "operators"

    operator_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="OBSERVER"
    )  # OBSERVER | PILOT | ADMIN
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
