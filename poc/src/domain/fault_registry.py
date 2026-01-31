"""Fault model registry (Registry Pattern)."""
from typing import Dict, Type
from .fault_model import FaultModel


class FaultModelRegistry:
    """Registry for fault model strategies."""
    
    def __init__(self):
        self._models: Dict[str, Type[FaultModel]] = {}
    
    def register(self, name: str, model_class: Type[FaultModel]):
        """
        Register a fault model class.
        
        Args:
            name: Unique identifier (e.g., "RF_LOSS_BURST")
            model_class: FaultModel subclass
        """
        if not issubclass(model_class, FaultModel):
            raise TypeError(f"{model_class} must inherit from FaultModel")
        self._models[name] = model_class
    
    def create(self, name: str, **kwargs) -> FaultModel:
        """
        Create fault model instance.
        
        Args:
            name: Registered fault name
            **kwargs: Arguments passed to fault model constructor
            
        Returns:
            Fault model instance
            
        Raises:
            KeyError: If fault name not registered
        """
        if name not in self._models:
            raise KeyError(f"Fault model '{name}' not registered")
        
        model_class = self._models[name]
        return model_class(**kwargs)
    
    def list_registered(self) -> list[str]:
        """List all registered fault names."""
        return list(self._models.keys())
