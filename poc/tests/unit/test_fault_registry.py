"""Unit tests for FaultModelRegistry (TDD style)."""
import pytest
from poc.src.domain.fault_registry import FaultModelRegistry
from poc.src.domain.rf_loss_burst import RFLossBurstFault
from poc.src.domain.fault_model import FaultModel


class TestFaultModelRegistry:
    """Test fault model registry."""
    
    def test_register_fault_model(self):
        """Should register fault model class."""
        registry = FaultModelRegistry()
        
        registry.register("RF_LOSS_BURST", RFLossBurstFault)
        
        assert "RF_LOSS_BURST" in registry.list_registered()
    
    def test_create_fault_instance(self):
        """Should create fault model instance with config."""
        registry = FaultModelRegistry()
        registry.register("RF_LOSS_BURST", RFLossBurstFault)
        
        fault = registry.create("RF_LOSS_BURST", every_sec=180.0, down_sec=8.0)
        
        assert isinstance(fault, RFLossBurstFault)
        assert fault.every_sec == 180.0
        assert fault.down_sec == 8.0
    
    def test_create_unregistered_fault_raises_error(self):
        """Should raise KeyError for unregistered fault."""
        registry = FaultModelRegistry()
        
        with pytest.raises(KeyError, match="not registered"):
            registry.create("UNKNOWN_FAULT")
    
    def test_register_non_fault_model_raises_error(self):
        """Should raise TypeError if class doesn't inherit FaultModel."""
        registry = FaultModelRegistry()
        
        class NotAFault:
            pass
        
        with pytest.raises(TypeError, match="must inherit from FaultModel"):
            registry.register("INVALID", NotAFault)
    
    def test_list_registered_empty_initially(self):
        """Registry should be empty initially."""
        registry = FaultModelRegistry()
        
        assert registry.list_registered() == []
    
    def test_register_multiple_faults(self):
        """Should register multiple fault models."""
        registry = FaultModelRegistry()
        
        # Create dummy fault for testing
        class DummyFault(FaultModel):
            def apply(self, telemetry):
                return telemetry, []
            def reset(self):
                pass
        
        registry.register("RF_LOSS_BURST", RFLossBurstFault)
        registry.register("DUMMY", DummyFault)
        
        registered = registry.list_registered()
        assert "RF_LOSS_BURST" in registered
        assert "DUMMY" in registered
        assert len(registered) == 2
