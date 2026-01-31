"""
Thrust shortfall fault model.

Simulates motor/propeller thrust loss causing altitude drop.
"""

import time
from typing import Dict, List, Optional, Tuple

from .fault_model import FaultModel
from .telemetry import Position, Telemetry


class ThrustShortfallFault(FaultModel):
    """
    Simulates periodic thrust shortfall causing altitude loss.
    
    Parameters:
        every_sec: How often (in seconds) the fault occurs
        duration_sec: How long (in seconds) each fault lasts
        alt_loss_mps: Altitude loss rate in meters per second
    """
    
    def __init__(
        self,
        every_sec: float = 120.0,
        duration_sec: float = 10.0,
        alt_loss_mps: float = 2.0
    ):
        self.every_sec = every_sec
        self.duration_sec = duration_sec
        self.alt_loss_mps = alt_loss_mps
        
        # Track last fault time per drone
        self._last_fault: Dict[str, float] = {}
        # Track fault start time per drone (for calculating cumulative altitude loss)
        self._fault_start: Dict[str, float] = {}
    
    def apply(self, telemetry: Telemetry) -> Tuple[Optional[Telemetry], List[str]]:
        """
        Apply thrust shortfall by reducing altitude.
        
        Returns (modified_telemetry, ["THRUST_SHORTFALL"]) when active,
        (telemetry, []) when inactive.
        """
        now = time.time()
        drone_id = telemetry.drone_id
        
        # Initialize per-drone state
        if drone_id not in self._last_fault:
            # Start with fault having ended duration_sec + 1 second ago
            self._last_fault[drone_id] = now - self.duration_sec - 1.0
            self._fault_start[drone_id] = 0.0
        
        # Check if enough time has passed to trigger fault
        time_since_last = now - self._last_fault[drone_id]
        if time_since_last >= self.every_sec:
            # Only reset fault_start if this is a NEW cycle (fault was inactive)
            if (now - self._last_fault[drone_id]) >= self.duration_sec:
                self._fault_start[drone_id] = now
            self._last_fault[drone_id] = now
        
        # Check if fault is currently active
        if (now - self._last_fault[drone_id]) < self.duration_sec:
            # Calculate altitude loss based on time in fault
            time_in_fault = now - self._fault_start[drone_id]
            # Apply minimum loss to ensure immediate effect (at least 0.01 seconds worth)
            time_in_fault = max(time_in_fault, 0.01)
            altitude_loss = self.alt_loss_mps * time_in_fault
            
            modified_position = Position(
                lat=telemetry.position.lat,
                lon=telemetry.position.lon,
                alt_m=max(0.0, telemetry.position.alt_m - altitude_loss)  # Don't go below ground
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
            
            return modified_telemetry, ["THRUST_SHORTFALL"]
        
        return telemetry, []
    
    def reset(self):
        """Reset fault state (clear per-drone tracking)."""
        self._last_fault.clear()
        self._fault_start.clear()
