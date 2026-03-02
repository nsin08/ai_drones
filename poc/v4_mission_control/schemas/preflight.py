"""Preflight response schemas."""

from pydantic import BaseModel, Field


class SensorHealth(BaseModel):
    """Hardware-aware sensor readiness flags."""

    gyro_ok: bool
    accel_ok: bool
    compass_ok: bool
    ekf_ok: bool


class PreflightResponse(BaseModel):
    """Canonical W10 preflight contract."""

    drone_id: str
    prearm_ok: bool
    calibration_required: bool
    battery_pct: int
    gps_sats: int
    armed: bool
    mode: str
    prearm_failures: list[str] = Field(default_factory=list)
    sensor_health: SensorHealth
    last_calibrated_at: str | None = None
    timestamp: str
