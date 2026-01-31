"""Telemetry domain entity - immutable value object."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class Position:
    """Geographic position value object."""
    lat: float
    lon: float
    alt_m: float
    
    def __post_init__(self):
        if not -90 <= self.lat <= 90:
            raise ValueError(f"Invalid latitude: {self.lat}")
        if not -180 <= self.lon <= 180:
            raise ValueError(f"Invalid longitude: {self.lon}")
        if self.alt_m < 0:
            raise ValueError(f"Invalid altitude: {self.alt_m}")


@dataclass(frozen=True)
class Telemetry:
    """Telemetry value object - immutable."""
    drone_id: str
    timestamp: float
    position: Position
    battery_pct: float
    velocity_mps: float = 0.0
    armed: bool = False
    mode: str = "GUIDED"
    
    def __post_init__(self):
        if not self.drone_id:
            raise ValueError("drone_id cannot be empty")
        if not 0 <= self.battery_pct <= 100:
            raise ValueError(f"Invalid battery: {self.battery_pct}")
    
    @staticmethod
    def now_timestamp() -> float:
        return datetime.now(timezone.utc).timestamp()
    
    def with_battery(self, new_pct: float) -> "Telemetry":
        """Return new instance with updated battery (immutable)."""
        return Telemetry(
            drone_id=self.drone_id,
            timestamp=self.timestamp,
            position=self.position,
            battery_pct=new_pct,
            velocity_mps=self.velocity_mps,
            armed=self.armed,
            mode=self.mode
        )
