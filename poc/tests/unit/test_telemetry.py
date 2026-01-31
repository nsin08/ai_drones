"""Unit tests for Telemetry entity (TDD style)."""
import pytest
from poc.src.domain.telemetry import Telemetry, Position


class TestPosition:
    """Test Position value object."""
    
    def test_create_valid_position(self):
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        assert pos.lat == 28.6139
        assert pos.lon == 77.2090
        assert pos.alt_m == 20.0
    
    def test_position_is_immutable(self):
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        with pytest.raises(AttributeError):
            pos.lat = 30.0  # Should fail (frozen dataclass)
    
    def test_invalid_latitude(self):
        with pytest.raises(ValueError, match="Invalid latitude"):
            Position(lat=91.0, lon=77.0, alt_m=20.0)
    
    def test_invalid_longitude(self):
        with pytest.raises(ValueError, match="Invalid longitude"):
            Position(lat=28.0, lon=181.0, alt_m=20.0)
    
    def test_invalid_altitude(self):
        with pytest.raises(ValueError, match="Invalid altitude"):
            Position(lat=28.0, lon=77.0, alt_m=-10.0)


class TestTelemetry:
    """Test Telemetry value object."""
    
    def test_create_valid_telemetry(self):
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        t = Telemetry(
            drone_id="D001",
            timestamp=1234567890.0,
            position=pos,
            battery_pct=85.0
        )
        assert t.drone_id == "D001"
        assert t.timestamp == 1234567890.0
        assert t.position == pos
        assert t.battery_pct == 85.0
    
    def test_telemetry_is_immutable(self):
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        t = Telemetry(drone_id="D001", timestamp=123.0, position=pos, battery_pct=100.0)
        with pytest.raises(AttributeError):
            t.drone_id = "D002"  # Should fail
    
    def test_invalid_battery_pct(self):
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        with pytest.raises(ValueError, match="Invalid battery"):
            Telemetry(drone_id="D001", timestamp=123.0, position=pos, battery_pct=150.0)
    
    def test_empty_drone_id(self):
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        with pytest.raises(ValueError, match="drone_id cannot be empty"):
            Telemetry(drone_id="", timestamp=123.0, position=pos, battery_pct=100.0)
    
    def test_with_battery_returns_new_instance(self):
        pos = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
        t1 = Telemetry(drone_id="D001", timestamp=123.0, position=pos, battery_pct=100.0)
        t2 = t1.with_battery(80.0)
        
        # Original unchanged
        assert t1.battery_pct == 100.0
        # New instance has updated battery
        assert t2.battery_pct == 80.0
        # Other fields preserved
        assert t2.drone_id == "D001"
        assert t2.position == pos
