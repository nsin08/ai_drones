"""
Unit tests for BATTERY_SAG fault model.
"""

import time

from poc.src.domain.battery_sag import BatterySagFault
from poc.src.domain.telemetry import Position, Telemetry


def test_battery_instantiation():
    """Test battery fault can be instantiated with default and custom params."""
    # Default params
    fault = BatterySagFault()
    assert fault.every_sec == 150.0
    assert fault.duration_sec == 12.0
    assert fault.sag_pct_per_sec == 1.5
    
    # Custom params
    fault = BatterySagFault(every_sec=60.0, duration_sec=5.0, sag_pct_per_sec=2.0)
    assert fault.every_sec == 60.0
    assert fault.duration_sec == 5.0
    assert fault.sag_pct_per_sec == 2.0


def test_battery_activation():
    """Test battery fault activates on schedule (periodic pattern)."""
    fault = BatterySagFault(every_sec=0.0, duration_sec=10.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # First call should activate (every_sec=0.0)
    result, faults = fault.apply(telemetry)
    assert "BATTERY_SAG" in faults


def test_battery_loss():
    """Test battery fault reduces battery percentage when active."""
    fault = BatterySagFault(every_sec=0.0, duration_sec=10.0, sag_pct_per_sec=2.0)
    
    original_battery = 80.0
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=original_battery
    )
    
    # First call activates fault
    result, faults = fault.apply(telemetry)
    assert "BATTERY_SAG" in faults
    
    # Battery should be reduced (minimum 0.01s worth of loss)
    assert result is not None
    assert result.battery_pct < original_battery
    
    # Wait a bit for more loss
    time.sleep(0.1)
    result2, faults2 = fault.apply(telemetry)
    
    # Loss accumulates based on time since fault start
    assert result2.battery_pct < original_battery - 0.15  # At least 0.15s * 2%/s loss


def test_battery_sag_rate():
    """Test battery sag rate matches configured value."""
    sag_pct_per_sec = 5.0
    fault = BatterySagFault(every_sec=0.0, duration_sec=10.0, sag_pct_per_sec=sag_pct_per_sec)
    
    original_battery = 80.0
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=original_battery
    )
    
    # Activate fault
    result1, _ = fault.apply(telemetry)
    
    # Wait known duration
    sleep_time = 0.2
    time.sleep(sleep_time)
    result2, _ = fault.apply(telemetry)
    
    # Calculate actual loss
    battery_lost = original_battery - result2.battery_pct
    
    # Loss accumulates from fault start
    expected_min_loss = sag_pct_per_sec * sleep_time * 0.8  # 80% of expected (timing jitter)
    expected_max_loss = sag_pct_per_sec * (sleep_time + 0.1)  # Allow extra for timing
    
    assert battery_lost >= expected_min_loss
    assert battery_lost <= expected_max_loss


def test_battery_duration():
    """Test battery fault respects duration parameter."""
    duration = 0.1
    fault = BatterySagFault(every_sec=0.0, duration_sec=duration)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # Fault should be active immediately
    result_during, faults_during = fault.apply(telemetry)
    assert "BATTERY_SAG" in faults_during
    
    # Still active immediately after
    result_still, faults_still = fault.apply(telemetry)
    assert "BATTERY_SAG" in faults_still
    
    # Wait for duration to expire
    time.sleep(duration + 0.05)
    
    # Fault expired, but retriggered immediately (every_sec=0.0)
    result_after, faults_after = fault.apply(telemetry)
    assert "BATTERY_SAG" in faults_after


def test_battery_recovery():
    """Test telemetry unchanged after fault recovery (between cycles)."""
    # Use non-zero every_sec to create gap between cycles
    fault = BatterySagFault(every_sec=1.0, duration_sec=0.05)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # First call activates fault
    result_active, faults_active = fault.apply(telemetry)
    assert "BATTERY_SAG" in faults_active
    
    # Wait for fault to expire (but not long enough for next cycle)
    time.sleep(0.1)
    
    # Should be in recovery period (no fault)
    result_recovery, faults_recovery = fault.apply(telemetry)
    assert "BATTERY_SAG" not in faults_recovery
    assert result_recovery == telemetry


def test_battery_multi_drone():
    """Test battery fault tracks state independently per drone."""
    fault = BatterySagFault(every_sec=0.0, duration_sec=10.0)
    
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
    
    assert "BATTERY_SAG" in faults1
    assert "BATTERY_SAG" in faults2
    
    # Both should have battery loss
    assert result1.battery_pct < 80.0
    assert result2.battery_pct < 75.0


def test_battery_no_fault_passthrough():
    """Test telemetry passes through unchanged when fault inactive."""
    # Use large every_sec so fault doesn't activate immediately
    fault = BatterySagFault(every_sec=1000.0, duration_sec=5.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # Fault should not be active
    result, faults = fault.apply(telemetry)
    assert "BATTERY_SAG" not in faults
    assert result == telemetry


def test_battery_zero_limit():
    """Test battery fault doesn't reduce battery below 0%."""
    fault = BatterySagFault(every_sec=0.0, duration_sec=10.0, sag_pct_per_sec=1000.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=10.0
    )
    
    # Activate fault with extreme loss rate
    result, faults = fault.apply(telemetry)
    assert "BATTERY_SAG" in faults
    
    # Battery should not go below 0%
    assert result.battery_pct >= 0.0
