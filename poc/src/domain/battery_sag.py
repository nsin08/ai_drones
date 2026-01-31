"""
Battery sag fault model.

Simulates battery voltage sag under load causing battery percentage drops.
"""

import time
from typing import Dict, List, Optional, Tuple

from poc.src.domain.fault_model import FaultModel
from poc.src.domain.telemetry import Telemetry


class BatterySagFault(FaultModel):
    """
    Simulates periodic battery sag causing battery percentage drops.
    
    Parameters:
        every_sec: How often (in seconds) the fault occurs
        duration_sec: How long (in seconds) each fault lasts
        sag_pct_per_sec: Battery percentage drop rate per second
    """
    
    def __init__(
        self,
        every_sec: float = 150.0,
        duration_sec: float = 12.0,
        sag_pct_per_sec: float = 1.5
    ):
        self.every_sec = every_sec
        self.duration_sec = duration_sec
        self.sag_pct_per_sec = sag_pct_per_sec
        
        # Track last fault time per drone
        self._last_fault: Dict[str, float] = {}
        # Track fault start time per drone (for calculating cumulative battery loss)
        self._fault_start: Dict[str, float] = {}
    
    def apply(self, telemetry: Telemetry) -> Tuple[Optional[Telemetry], List[str]]:
        """
        Apply battery sag by reducing battery percentage.
        
        Returns (modified_telemetry, ["BATTERY_SAG"]) when active,
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
            # Calculate battery loss based on time in fault
            time_in_fault = now - self._fault_start[drone_id]
            # Apply minimum loss to ensure immediate effect (at least 0.01 seconds worth)
            time_in_fault = max(time_in_fault, 0.01)
            battery_loss = self.sag_pct_per_sec * time_in_fault
            
            modified_telemetry = Telemetry(
                drone_id=telemetry.drone_id,
                timestamp=telemetry.timestamp,
                position=telemetry.position,
                battery_pct=max(0.0, telemetry.battery_pct - battery_loss),  # Don't go below 0%
                velocity_mps=telemetry.velocity_mps,
                armed=telemetry.armed,
                mode=telemetry.mode
            )
            
            return modified_telemetry, ["BATTERY_SAG"]
        
        return telemetry, []
    
    def reset(self):
        """Reset fault state (clear per-drone tracking)."""
        self._last_fault.clear()
        self._fault_start.clear()
