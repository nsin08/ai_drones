"""
EKF (Extended Kalman Filter) health fault model.

Simulates EKF failures causing noisy position estimates via Gaussian noise injection.
"""

import random
import time
from typing import Dict, List, Optional, Tuple

from .fault_model import FaultModel
from .telemetry import Position, Telemetry


class EKFUnhealthyFault(FaultModel):
    """
    Simulates periodic EKF unhealthy state by injecting Gaussian position noise.
    
    Parameters:
        every_sec: How often (in seconds) the fault occurs
        duration_sec: How long (in seconds) each fault lasts
        noise_stddev_m: Standard deviation of Gaussian noise in meters
    """
    
    def __init__(
        self,
        every_sec: float = 90.0,
        duration_sec: float = 8.0,
        noise_stddev_m: float = 15.0
    ):
        self.every_sec = every_sec
        self.duration_sec = duration_sec
        self.noise_stddev_m = noise_stddev_m
        
        # Track last fault time per drone
        self._last_fault: Dict[str, float] = {}
    
    def apply(self, telemetry: Telemetry) -> Tuple[Optional[Telemetry], List[str]]:
        """
        Apply EKF unhealthy fault by injecting Gaussian position noise.
        
        Returns (modified_telemetry, ["EKF_UNHEALTHY"]) when active,
        (telemetry, []) when inactive.
        """
        now = time.time()
        drone_id = telemetry.drone_id
        
        # Initialize per-drone state
        if drone_id not in self._last_fault:
            # Start with fault having ended duration_sec + 1 second ago
            self._last_fault[drone_id] = now - self.duration_sec - 1.0
        
        # Check if enough time has passed to trigger fault
        time_since_last = now - self._last_fault[drone_id]
        if time_since_last >= self.every_sec:
            self._last_fault[drone_id] = now
        
        # Check if fault is currently active
        if (now - self._last_fault[drone_id]) < self.duration_sec:
            # Apply Gaussian noise to position
            noise_x = random.gauss(0, self.noise_stddev_m)
            noise_y = random.gauss(0, self.noise_stddev_m)
            noise_z = random.gauss(0, self.noise_stddev_m)
            
            # Convert meters to degrees (approximate: 1m ≈ 1/111000 degrees at equator)
            lat_offset = noise_x / 111000.0
            lon_offset = noise_y / 111000.0
            
            modified_position = Position(
                lat=telemetry.position.lat + lat_offset,
                lon=telemetry.position.lon + lon_offset,
                alt_m=telemetry.position.alt_m + noise_z
            )
            
            modified_telemetry = Telemetry(
                drone_id=telemetry.drone_id,
                timestamp=telemetry.timestamp,
                position=modified_position,
                battery_pct=telemetry.battery_pct,
                velocity_mps=telemetry.velocity_mps,
                armed=telemetry.armed,
                mode=telemetry.mode
            )
            
            return modified_telemetry, ["EKF_UNHEALTHY"]
        
        return telemetry, []
    
    def reset(self):
        """Reset fault state (clear per-drone tracking)."""
        self._last_fault.clear()
