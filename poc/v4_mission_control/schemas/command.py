"""Command request/response schemas."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CommandStatus(str, Enum):
    """Pinned command lifecycle states for W10."""

    REQUESTED = "REQUESTED"
    RETRYING = "RETRYING"
    ACKED = "ACKED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class CommandRequest(BaseModel):
    """Canonical W10 command submission request."""

    drone_id: str
    command: str
    params: dict[str, Any] = Field(default_factory=dict)
    client_request_id: str | None = None
    requested_by: str | None = None

    @field_validator("drone_id")
    @classmethod
    def validate_drone_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("drone_id is required")
        return normalized

    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("command is required")
        return normalized


class CommandAcceptedResponse(BaseModel):
    """Accepted command response."""

    cmd_id: UUID
    accepted: bool = True
    status: CommandStatus
    drone_id: str
    command: str
    attempt_count: int
    rejection_reason: str | None = None
    created_at: str


class CommandRejectedResponse(BaseModel):
    """Rejected command response."""

    accepted: bool = False
    status: CommandStatus = CommandStatus.REJECTED
    drone_id: str
    command: str
    rejection_reason: str


class CommandHistoryItem(BaseModel):
    """One row in command history."""

    cmd_id: UUID
    drone_id: str
    command: str
    status: CommandStatus
    attempt_count: int
    created_at: str


class CommandHistoryResponse(BaseModel):
    """Recent command history response."""

    items: list[CommandHistoryItem]
