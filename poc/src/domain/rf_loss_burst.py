"""RF Loss Burst fault model implementation."""
import time
from typing import Optional, List, Tuple, Dict
from .fault_model import FaultModel
from .telemetry import Telemetry


class RFLossBurstFault(FaultModel):
    """Simulates periodic RF loss bursts (telemetry drops)."""
    
    def __init__(self, every_sec: float = 180.0, down_sec: float = 8.0):
        """
        Initialize RF loss burst fault.
        
        Args:
            every_sec: Burst occurs every N seconds
            down_sec: Burst lasts for N seconds
        """
        self.every_sec = every_sec
        self.down_sec = down_sec
        self._last_burst: Dict[str, float] = {}
    
    def apply(self, telemetry: Telemetry) -> Tuple[Optional[Telemetry], List[str]]:
        """
        Apply RF loss burst logic.
        
        Returns None (drops message) if in burst window.
        """
        now = time.time()
        drone_id = telemetry.drone_id
        
        # Initialize tracking for this drone
        if drone_id not in self._last_burst:
            self._last_burst[drone_id] = 0.0
        
        # Check if it's time to start a new burst
        time_since_last = now - self._last_burst[drone_id]
        if time_since_last >= self.every_sec:
            self._last_burst[drone_id] = now
        
        # Check if we're currently in a burst
        burst_age = now - self._last_burst[drone_id]
        if burst_age < self.down_sec:
            # Drop message (return None)
            return None, ["RF_LOSS_BURST"]
        
        # Pass message through
        return telemetry, []
    
    def reset(self):
        """Reset burst tracking."""
        self._last_burst.clear()
