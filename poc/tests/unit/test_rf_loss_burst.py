"""Unit tests for RFLossBurstFault (TDD style)."""
import time
import pytest
from poc.src.domain.telemetry import Telemetry, Position
from poc.src.domain.rf_loss_burst import RFLossBurstFault


class TestRFLossBurstFault:
    """Test RF loss burst fault model."""
    
    @pytest.fixture
    def telemetry(self):
        """Sample telemetry for testing."""
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        return Telemetry(
            drone_id="D001",
            timestamp=time.time(),
            position=pos,
            battery_pct=100.0
        )
    
    def test_passes_message_initially(self, telemetry):
        """First message should pass (no burst yet)."""
        fault = RFLossBurstFault(every_sec=10.0, down_sec=3.0)
        
        result, faults = fault.apply(telemetry)
        
        assert result is not None  # Message passed
        assert faults == []  # No faults active
    
    def test_drops_message_during_burst(self, telemetry):
        """Message should be dropped during burst window."""
        fault = RFLossBurstFault(every_sec=10.0, down_sec=3.0)
        
        # Simulate time into burst (2s into 3s burst)
        fault._last_burst["D001"] = time.time() - 2.0
        
        result, faults = fault.apply(telemetry)
        
        assert result is None  # Message dropped
        assert "RF_LOSS_BURST" in faults
    
    def test_passes_message_after_burst_ends(self, telemetry):
        """Message should pass after burst ends."""
        fault = RFLossBurstFault(every_sec=10.0, down_sec=3.0)
        
        # Simulate time after burst (5s after burst started, burst lasts 3s)
        fault._last_burst["D001"] = time.time() - 5.0
        
        result, faults = fault.apply(telemetry)
        
        assert result is not None  # Message passed
        assert faults == []
    
    def test_starts_new_burst_after_interval(self, telemetry):
        """New burst should start after 'every_sec' interval."""
        fault = RFLossBurstFault(every_sec=10.0, down_sec=3.0)
        
        # Simulate time past interval (11s since last burst)
        fault._last_burst["D001"] = time.time() - 11.0
        
        result, faults = fault.apply(telemetry)
        
        # Should drop (new burst started)
        assert result is None
        assert "RF_LOSS_BURST" in faults
    
    def test_tracks_multiple_drones_independently(self):
        """Each drone should have independent burst tracking."""
        fault = RFLossBurstFault(every_sec=10.0, down_sec=3.0)
        
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        t1 = Telemetry(drone_id="D001", timestamp=time.time(), position=pos, battery_pct=100.0)
        t2 = Telemetry(drone_id="D002", timestamp=time.time(), position=pos, battery_pct=100.0)
        
        # D001 in burst
        fault._last_burst["D001"] = time.time() - 1.0
        
        # D001 should drop
        result1, _ = fault.apply(t1)
        assert result1 is None
        
        # D002 should pass (no burst)
        result2, _ = fault.apply(t2)
        assert result2 is not None
    
    def test_reset_clears_tracking(self, telemetry):
        """Reset should clear all burst tracking."""
        fault = RFLossBurstFault(every_sec=10.0, down_sec=3.0)
        
        # Set up burst state
        fault._last_burst["D001"] = time.time() - 1.0
        assert len(fault._last_burst) == 1
        
        # Reset
        fault.reset()
        
        assert len(fault._last_burst) == 0
