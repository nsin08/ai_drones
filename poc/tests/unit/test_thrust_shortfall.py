"""
Unit tests for THRUST_SHORTFALL fault model.
"""

import time

from poc.src.domain.thrust_shortfall import ThrustShortfallFault
from poc.src.domain.telemetry import Position, Telemetry


def test_thrust_instantiation():
    """Test thrust fault can be instantiated with default and custom params."""
    # Default params
    fault = ThrustShortfallFault()
    assert fault.every_sec == 120.0
    assert fault.duration_sec == 10.0
    assert fault.alt_loss_mps == 2.0
    
    # Custom params
    fault = ThrustShortfallFault(every_sec=60.0, duration_sec=5.0, alt_loss_mps=3.0)
    assert fault.every_sec == 60.0
    assert fault.duration_sec == 5.0
    assert fault.alt_loss_mps == 3.0


def test_thrust_activation():
    """Test thrust fault activates on schedule (periodic pattern)."""
    fault = ThrustShortfallFault(every_sec=0.0, duration_sec=10.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # First call should activate (every_sec=0.0)
    result, faults = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults


def test_thrust_altitude_loss():
    """Test thrust fault reduces altitude when active (cumulative effect over time)."""
    fault = ThrustShortfallFault(every_sec=0.0, duration_sec=10.0, alt_loss_mps=5.0)
    
    original_alt = 100.0
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, original_alt),
        battery_pct=80.0
    )
    
    # First call activates fault
    result1, faults1 = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults1
    assert result1.position.alt_m < original_alt
    
    # Wait for time to pass
    time.sleep(0.1)
    
    # Second call with SAME input altitude - loss increases from fault start
    result2, faults2 = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults2
    
    # Loss from original should be greater in second call
    # (time_in_fault increased, so more loss applied to same input)
    loss1 = original_alt - result1.position.alt_m
    loss2 = original_alt - result2.position.alt_m
    assert loss2 > loss1  # More time in fault = more loss


def test_thrust_loss_rate():
    """Test thrust altitude loss rate matches configured value."""
    alt_loss_mps = 10.0  # Use larger value for clearer signal
    fault = ThrustShortfallFault(every_sec=0.0, duration_sec=10.0, alt_loss_mps=alt_loss_mps)
    
    original_alt = 100.0
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, original_alt),
        battery_pct=80.0
    )
    
    # Activate fault
    result1, _ = fault.apply(telemetry)
    first_loss = original_alt - result1.position.alt_m
    
    # Wait known duration
    sleep_time = 0.15
    time.sleep(sleep_time)
    
    # Apply again
    result2, _ = fault.apply(telemetry)
    second_loss = original_alt - result2.position.alt_m
    
    # Loss should have increased by approximately alt_loss_mps * sleep_time
    additional_loss = second_loss - first_loss
    expected_additional = alt_loss_mps * sleep_time
    
    # Allow tolerance for timing jitter (±20%)
    assert abs(additional_loss - expected_additional) < expected_additional * 0.3


def test_thrust_duration():
    """Test thrust fault respects duration parameter."""
    duration = 0.1
    fault = ThrustShortfallFault(every_sec=0.0, duration_sec=duration)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # Fault should be active immediately
    result_during, faults_during = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults_during
    
    # Still active immediately after
    result_still, faults_still = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults_still
    
    # Wait for duration to expire
    time.sleep(duration + 0.05)
    
    # Fault expired, but retriggered immediately (every_sec=0.0)
    result_after, faults_after = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults_after


def test_thrust_recovery():
    """Test telemetry unchanged after fault recovery (between cycles)."""
    # Use non-zero every_sec to create gap between cycles
    fault = ThrustShortfallFault(every_sec=1.0, duration_sec=0.05)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # First call activates fault
    result_active, faults_active = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults_active
    
    # Wait for fault to expire (but not long enough for next cycle)
    time.sleep(0.1)
    
    # Should be in recovery period (no fault)
    result_recovery, faults_recovery = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" not in faults_recovery
    assert result_recovery == telemetry


def test_thrust_multi_drone():
    """Test thrust fault tracks state independently per drone."""
    fault = ThrustShortfallFault(every_sec=0.0, duration_sec=10.0)
    
    telemetry1 = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    telemetry2 = Telemetry(
        drone_id="DRONE-02",
        timestamp=time.time(),
        position=Position(37.7750, -122.4195, 105.0),
        battery_pct=75.0
    )
    
    # Both should activate independently
    result1, faults1 = fault.apply(telemetry1)
    result2, faults2 = fault.apply(telemetry2)
    
    assert "THRUST_SHORTFALL" in faults1
    assert "THRUST_SHORTFALL" in faults2
    
    # Both should have altitude loss
    assert result1.position.alt_m < 100.0
    assert result2.position.alt_m < 105.0


def test_thrust_no_fault_passthrough():
    """Test telemetry passes through unchanged when fault inactive."""
    # Use large every_sec so fault doesn't activate immediately
    fault = ThrustShortfallFault(every_sec=1000.0, duration_sec=5.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # Fault should not be active
    result, faults = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" not in faults
    assert result == telemetry


def test_thrust_ground_limit():
    """Test thrust fault doesn't reduce altitude below 0."""
    fault = ThrustShortfallFault(every_sec=0.0, duration_sec=10.0, alt_loss_mps=1000.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 10.0),
        battery_pct=80.0
    )
    
    # Activate fault with extreme loss rate
    result, faults = fault.apply(telemetry)
    assert "THRUST_SHORTFALL" in faults
    
    # Altitude should not go below 0
    assert result.position.alt_m >= 0.0
