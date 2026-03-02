"""GNSS Multipath Fault Model

Simulates GNSS multipath interference that causes position offsets.
Common in urban canyons, near buildings, or under obstructions.
"""

import time
from typing import Optional, List, Tuple, Dict

from .fault_model import FaultModel
from .telemetry import Telemetry, Position


class GNSSMultipathFault(FaultModel):
    """Fault model simulating GNSS multipath interference.
    
    Causes position offset of ±offset_range meters for duration_sec seconds,
    then automatically recovers.
    
    Args:
        every_sec: Fault occurs every N seconds (default: 60.0)
        duration_sec: How long the fault lasts in seconds (default: 5.0s)
        offset_range: Maximum position offset in meters (default: 10.0m)
    """
    
    def __init__(
        self,
        every_sec: float = 60.0,
        duration_sec: float = 5.0,
        offset_range: float = 10.0
    ):
        self.every_sec = every_sec
        self.duration_sec = duration_sec
        self.offset_range = offset_range
        self._last_fault: Dict[str, float] = {}
        self._offsets: Dict[str, Tuple[float, float]] = {}
    
    def apply(self, telemetry: Telemetry) -> Tuple[Optional[Telemetry], List[str]]:
        """Apply GNSS multipath fault to telemetry.
        
        Args:
            telemetry: Input telemetry data
            
        Returns:
            Tuple of (modified telemetry, list of active fault codes)
        """
        now = time.time()
        drone_id = telemetry.drone_id
        
        # Initialize tracking for this drone (far enough in past that fault ended)
        if drone_id not in self._last_fault:
            self._last_fault[drone_id] = now - self.duration_sec - 1.0
        
        # Check if it's time to start a new fault
        time_since_last = now - self._last_fault[drone_id]
        if time_since_last >= self.every_sec:
            self._last_fault[drone_id] = now
            # Generate random offsets for this fault instance
            import random
            self._offsets[drone_id] = (
                random.uniform(-self.offset_range, self.offset_range),
                random.uniform(-self.offset_range, self.offset_range)
            )
        
        # Check if we're currently in a fault
        fault_age = now - self._last_fault[drone_id]
        if fault_age < self.duration_sec:
            # Apply position offset
            offset_x, offset_y = self._offsets.get(drone_id, (0.0, 0.0))
            
            return Telemetry(
                drone_id=telemetry.drone_id,
                timestamp=telemetry.timestamp,
                position=Position(
                    lat=telemetry.position.lat + (offset_x / 111000),
                    lon=telemetry.position.lon + (offset_y / 111000),
                    alt_m=telemetry.position.alt_m
                ),
                battery_pct=telemetry.battery_pct,
                velocity_mps=telemetry.velocity_mps,
                armed=telemetry.armed,
                mode=telemetry.mode
            ), ["GNSS_MULTIPATH"]
        
        # Pass message through
        return telemetry, []
    
    def reset(self):
        """Reset fault tracking."""
        self._last_fault.clear()
        self._offsets.clear()
