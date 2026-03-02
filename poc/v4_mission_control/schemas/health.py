"""Health response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Canonical bootstrap health response."""

    status: str
    service: str
    environment: str
    timestamp: str


class FleetHealthSummary(BaseModel):
    """Aggregate fleet health placeholder for W10."""

    healthy: int
    warning: int
    critical: int
    offline: int
    details: list[dict[str, Any]] = Field(default_factory=list)
