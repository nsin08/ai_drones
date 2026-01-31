"""Fault model interface (Strategy Pattern)."""
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from .telemetry import Telemetry


class FaultModel(ABC):
    """Abstract base for fault injection strategies."""
    
    @abstractmethod
    def apply(self, telemetry: Telemetry) -> Tuple[Optional[Telemetry], List[str]]:
        """
        Apply fault model to telemetry.
        
        Args:
            telemetry: Input telemetry data
            
        Returns:
            Tuple of:
            - Modified telemetry (None if message should be dropped)
            - List of active fault codes
        """
        pass
    
    @abstractmethod
    def reset(self):
        """Reset fault model state."""
        pass
