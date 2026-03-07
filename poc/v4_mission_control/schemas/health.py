"""Health response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Canonical bootstrap health response."""

    status: str
    service: str
    environment: str
    timestamp: str
    # W15: live connectivity state (None when unknown / not yet polled)
    mqtt_connected: bool | None = None
    inventory_available: bool | None = None
    # W10: auth mode visible to the demo presenter (Settings page)
    auth_enabled: bool = False


class DroneHealthResult(BaseModel):
    """Per-drone health score and classification."""

    drone_id: str
    score: float = Field(ge=0.0, le=1.0, description="[0, 1] composite health score")
    label: str = Field(
        description="GREEN | YELLOW | RED | OFFLINE",
    )
    battery_pct: float | None = None
    gps_sats: int | None = None
    ekf_ok: bool | None = None
    last_seen_at: str | None = None


class FleetHealthSummary(BaseModel):
    """Aggregate fleet health — real data from HealthService (W13)."""

    healthy: int
    warning: int
    critical: int
    offline: int
    details: list[dict[str, Any]] = Field(default_factory=list)
