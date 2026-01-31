"""
Unit tests for EKF_UNHEALTHY fault model.
"""

import time

from poc.src.domain.ekf_unhealthy import EKFUnhealthyFault
from poc.src.domain.telemetry import Position, Telemetry


def test_ekf_instantiation():
    """Test EKF fault can be instantiated with default and custom params."""
    # Default params
    fault = EKFUnhealthyFault()
    assert fault.every_sec == 90.0
    assert fault.duration_sec == 8.0
    assert fault.noise_stddev_m == 15.0
    
    # Custom params
    fault = EKFUnhealthyFault(every_sec=30.0, duration_sec=5.0, noise_stddev_m=20.0)
    assert fault.every_sec == 30.0
    assert fault.duration_sec == 5.0
    assert fault.noise_stddev_m == 20.0


def test_ekf_activation():
    """Test EKF fault activates on schedule (periodic pattern)."""
    fault = EKFUnhealthyFault(every_sec=0.0, duration_sec=10.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # First call should activate (every_sec=0.0)
    result, faults = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" in faults


def test_ekf_noise_applied():
    """Test EKF fault modifies position when active."""
    fault = EKFUnhealthyFault(every_sec=0.0, duration_sec=10.0, noise_stddev_m=10.0)
    
    original_pos = Position(37.7749, -122.4194, 100.0)
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=original_pos,
        battery_pct=80.0
    )
    
    result, faults = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" in faults
    
    # Position should change (noise applied)
    assert result is not None
    assert (result.position.lat != original_pos.lat or 
            result.position.lon != original_pos.lon or 
            result.position.alt_m != original_pos.alt_m)


def test_ekf_noise_magnitude():
    """Test EKF noise is within reasonable bounds (3-sigma rule: 99.7% within 3*stddev)."""
    stddev_m = 10.0
    fault = EKFUnhealthyFault(every_sec=0.0, duration_sec=10.0, noise_stddev_m=stddev_m)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # Run multiple times to check noise distribution
    max_offset_deg = (3 * stddev_m) / 111000.0  # 3-sigma in degrees
    max_offset_alt = 3 * stddev_m  # 3-sigma in meters
    
    for _ in range(20):
        result, faults = fault.apply(telemetry)
        if "EKF_UNHEALTHY" in faults:
            lat_diff = abs(result.position.lat - telemetry.position.lat)
            lon_diff = abs(result.position.lon - telemetry.position.lon)
            alt_diff = abs(result.position.alt_m - telemetry.position.alt_m)
            
            # Most samples should be within 3-sigma
            assert lat_diff <= max_offset_deg * 1.5  # Allow some margin
            assert lon_diff <= max_offset_deg * 1.5
            assert alt_diff <= max_offset_alt * 1.5


def test_ekf_duration():
    """Test EKF fault respects duration parameter."""
    duration = 0.1
    fault = EKFUnhealthyFault(every_sec=0.0, duration_sec=duration)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # Fault should be active immediately
    result_during, faults_during = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" in faults_during
    
    # Still active immediately after
    result_still, faults_still = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" in faults_still
    
    # Wait for duration to expire
    time.sleep(duration + 0.05)
    
    # Fault expired, but retriggered immediately (every_sec=0.0)
    result_after, faults_after = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" in faults_after


def test_ekf_recovery():
    """Test telemetry unchanged after fault recovery (between cycles)."""
    # Use non-zero every_sec to create gap between cycles
    fault = EKFUnhealthyFault(every_sec=1.0, duration_sec=0.05)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # First call activates fault
    result_active, faults_active = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" in faults_active
    
    # Wait for fault to expire (but not long enough for next cycle)
    time.sleep(0.1)
    
    # Should be in recovery period (no fault)
    result_recovery, faults_recovery = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" not in faults_recovery
    assert result_recovery == telemetry


def test_ekf_multi_drone():
    """Test EKF fault tracks state independently per drone."""
    fault = EKFUnhealthyFault(every_sec=0.0, duration_sec=10.0)
    
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
    
    assert "EKF_UNHEALTHY" in faults1
    assert "EKF_UNHEALTHY" in faults2
    
    # Noise should be different (independent random values)
    assert result1.position.lat != result2.position.lat or result1.position.lon != result2.position.lon


def test_ekf_no_fault_passthrough():
    """Test telemetry passes through unchanged when fault inactive."""
    # Use large every_sec so fault doesn't activate immediately
    fault = EKFUnhealthyFault(every_sec=1000.0, duration_sec=5.0)
    
    telemetry = Telemetry(
        drone_id="DRONE-01",
        timestamp=time.time(),
        position=Position(37.7749, -122.4194, 100.0),
        battery_pct=80.0
    )
    
    # Fault should not be active (every_sec=1000 means ~6 seconds since init, needs 1000)
    result, faults = fault.apply(telemetry)
    assert "EKF_UNHEALTHY" not in faults
    assert result == telemetry
