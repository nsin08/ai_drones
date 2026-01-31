"""
Battery sag fault model.

Simulates battery voltage sag under load causing temporary capacity drop.
"""

import time
from typing import Dict, List, Optional, Tuple

from poc.src.domain.fault_model import FaultModel
from poc.src.domain.telemetry import Telemetry


class BatterySagFault(FaultModel):
    """
    Simulates periodic battery sag (voltage drop under load).
    
    Parameters:
        every_sec: How often (in seconds) the fault occurs
        duration_sec: How long (in seconds) each fault lasts
        sag_pct: Battery percentage drop during sag
    """
    
    def __init__(
        self,
        every_sec: float = 150.0,
        duration_sec: float = 6.0,
        sag_pct: float = 15.0
    ):
        self.every_sec = every_sec
        self.duration_sec = duration_sec
        self.sag_pct = sag_pct
        
        # Track last fault time per drone
        self._last_fault: Dict[str, float] = {}
    
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
        
        # Check if enough time has passed to trigger fault
        time_since_last = now - self._last_fault[drone_id]
        if time_since_last >= self.every_sec:
            self._last_fault[drone_id] = now
        
        # Check if fault is currently active
        if (now - self._last_fault[drone_id]) < self.duration_sec:
            # Apply battery sag
            sagged_battery = max(0.0, telemetry.battery_pct - self.sag_pct)
            
            modified_telemetry = Telemetry(
                drone_id=telemetry.drone_id,
                timestamp=telemetry.timestamp,
                position=telemetry.position,
                battery_pct=sagged_battery,
                velocity_mps=telemetry.velocity_mps,
                armed=telemetry.armed,
                mode=telemetry.mode
            )
            
            return modified_telemetry, ["BATTERY_SAG"]
        
        return telemetry, []
    
    def reset(self):
        """Reset fault state (clear per-drone tracking)."""
        self._last_fault.clear()
