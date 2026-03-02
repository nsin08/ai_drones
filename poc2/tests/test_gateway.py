"""
poc2/tests/test_gateway.py
──────────────────────────
Unit tests for:
  - MavlinkProcessor._process() message mapping
  - MqttPublisher._telemetry_payload() schema validation
  - parse_ports_arg() multi-port CLI parsing
  - DroneSession state isolation (two sessions don't share state)

No hardware or MQTT broker required — all offline/unit tests.
"""

import sys
import threading
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "poc2"))

fake_mavutil = types.SimpleNamespace(
    mavlink=types.SimpleNamespace(
        MAV_MODE_FLAG_SAFETY_ARMED=128,
        MAV_CMD_COMPONENT_ARM_DISARM=400,
        enums={"MAV_TYPE": {}},
    ),
    mode_string_v10=lambda _msg: "STABILIZE",
)
fake_pymavlink = types.ModuleType("pymavlink")
fake_pymavlink.mavutil = fake_mavutil
sys.modules.setdefault("pymavlink", fake_pymavlink)

fake_paho = types.ModuleType("paho")
fake_paho_mqtt = types.ModuleType("paho.mqtt")
fake_paho_mqtt_client = types.ModuleType("paho.mqtt.client")


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass


fake_paho_mqtt_client.Client = _FakeClient
fake_paho_mqtt_client.CallbackAPIVersion = types.SimpleNamespace(VERSION2=object())
fake_paho.mqtt = fake_paho_mqtt
fake_paho_mqtt.client = fake_paho_mqtt_client
sys.modules.setdefault("paho", fake_paho)
sys.modules.setdefault("paho.mqtt", fake_paho_mqtt)
sys.modules.setdefault("paho.mqtt.client", fake_paho_mqtt_client)

from drone_gateway import (
    FORCE_ARM_MAGIC,
    _empty_state,
    MavlinkProcessor,
    MqttPublisher,
    DroneSession,
    parse_ports_arg,
    _rad2deg,
)


# ─── Helpers: mock MAVLink message ────────────────────────────────────────────

def _mock_msg(msg_type: str, **fields):
    """Create a lightweight mock that quacks like a pymavlink message."""
    msg = MagicMock()
    msg.get_type.return_value = msg_type
    for k, v in fields.items():
        setattr(msg, k, v)
    return msg


def _make_processor():
    state = _empty_state()
    lock  = threading.Lock()
    proc  = MavlinkProcessor.__new__(MavlinkProcessor)
    proc.port  = "COM_TEST"
    proc.baud  = 57600
    proc.state = state
    proc.lock  = lock
    proc.conn  = None
    # Inject mock mavutil so we can test without hardware
    return proc, state, lock


# ─── MavlinkProcessor._process tests ─────────────────────────────────────────

class TestMavlinkProcessorHeartbeat:
    def test_heartbeat_sets_armed_false(self):
        proc, state, lock = _make_processor()
        # Patch mavutil at the module level the processor uses
        mock_mavutil = MagicMock()
        mock_mavutil.mode_string_v10.return_value = "STABILIZE"
        mock_mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED = 128
        mock_mavutil.mavlink.enums = {"MAV_TYPE": {2: MagicMock(name="MAV_TYPE_QUADROTOR")}}
        with patch("drone_gateway.mavutil", mock_mavutil):
            msg = _mock_msg("HEARTBEAT", base_mode=0, custom_mode=0, type=2)
            proc._process(msg)
        assert state["armed"] is False
        assert state["mode"] == "STABILIZE"

    def test_heartbeat_sets_armed_true(self):
        proc, state, lock = _make_processor()
        mock_mavutil = MagicMock()
        mock_mavutil.mode_string_v10.return_value = "AUTO"
        MAV_ARMED = 128
        mock_mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED = MAV_ARMED
        mock_mavutil.mavlink.enums = {"MAV_TYPE": {2: MagicMock(name="MAV_TYPE_QUADROTOR")}}
        with patch("drone_gateway.mavutil", mock_mavutil):
            msg = _mock_msg("HEARTBEAT", base_mode=MAV_ARMED | 0b10000, custom_mode=0, type=2)
            proc._process(msg)
        assert state["armed"] is True

    def test_msg_count_increments(self):
        proc, state, lock = _make_processor()
        mock_mavutil = MagicMock()
        mock_mavutil.mode_string_v10.return_value = "STABILIZE"
        mock_mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED = 128
        mock_mavutil.mavlink.enums = {"MAV_TYPE": {}}
        with patch("drone_gateway.mavutil", mock_mavutil):
            for _ in range(5):
                msg = _mock_msg("HEARTBEAT", base_mode=0, custom_mode=0, type=0)
                proc._process(msg)
        assert state["msg_count"] == 5


class TestMavlinkProcessorGPS:
    def test_gps_raw_int(self):
        proc, state, _ = _make_processor()
        msg = _mock_msg("GPS_RAW_INT",
                        fix_type=3,
                        satellites_visible=9,
                        eph=90,    # hdop × 100
                        lat=247157240,  # 24.715724 × 1e7
                        lon=788061150)  # 78.806115 × 1e7
        proc._process(msg)
        assert state["gps_fix"] == 3
        assert state["satellites_visible"] == 9
        assert abs(state["latitude"] - 24.7157240) < 1e-5
        assert abs(state["longitude"] - 78.8061150) < 1e-5
        assert abs(state["hdop"] - 0.90) < 0.01

    def test_gps_zero_lat_lon_ignored(self):
        """lat=0 lon=0 is uninitialized GPS; should not overwrite valid data."""
        proc, state, _ = _make_processor()
        state["latitude"]  = 24.715724
        state["longitude"] = 78.806115
        msg = _mock_msg("GPS_RAW_INT", fix_type=0, satellites_visible=0, eph=0, lat=0, lon=0)
        proc._process(msg)
        assert state["latitude"] == 24.715724
        assert state["longitude"] == 78.806115


class TestMavlinkProcessorBattery:
    def test_sys_status(self):
        proc, state, _ = _make_processor()
        msg = _mock_msg("SYS_STATUS",
                        voltage_battery=11070,   # mV
                        current_battery=9,       # 0.1A units (0.09A)
                        battery_remaining=94)
        proc._process(msg)
        assert state["battery_pct"] == 94
        assert abs(state["voltage_v"] - 11.07) < 0.01
        assert abs(state["current_a"] - 0.09) < 0.01


class TestMavlinkProcessorAttitude:
    def test_attitude_in_degrees(self):
        import math
        proc, state, _ = _make_processor()
        msg = _mock_msg("ATTITUDE",
                        roll=-0.01466,    # ≈ -0.84°
                        pitch=-0.05969,   # ≈ -3.42°
                        yaw=-0.76300)     # ≈ -43.7°
        proc._process(msg)
        assert abs(state["roll_deg"] - _rad2deg(-0.01466)) < 0.01
        assert abs(state["pitch_deg"] - _rad2deg(-0.05969)) < 0.01

    def test_heading_deg_derived_from_yaw(self):
        import math
        proc, state, _ = _make_processor()
        msg = _mock_msg("ATTITUDE", roll=0.0, pitch=0.0, yaw=math.pi)   # 180°
        proc._process(msg)
        assert abs(state["heading_deg"] - 180.0) < 0.5


class TestMavlinkProcessorEKFAndVibration:
    def test_ekf_healthy(self):
        proc, state, _ = _make_processor()
        msg = _mock_msg("EKF_STATUS_REPORT", flags=0x01)
        proc._process(msg)
        assert state["ekf_ok"] is True

    def test_ekf_unhealthy(self):
        proc, state, _ = _make_processor()
        msg = _mock_msg("EKF_STATUS_REPORT", flags=0x00)
        proc._process(msg)
        assert state["ekf_ok"] is False

    def test_vibration_values(self):
        proc, state, _ = _make_processor()
        msg = _mock_msg("VIBRATION", vibration_x=0.02, vibration_y=0.02, vibration_z=0.03)
        proc._process(msg)
        assert abs(state["vibe_x"] - 0.02) < 0.001
        assert abs(state["vibe_z"] - 0.03) < 0.001


class TestMavlinkProcessorStatusText:
    def test_prearm_failure_flagged(self):
        proc, state, _ = _make_processor()
        msg = _mock_msg("STATUSTEXT", severity=3, text="PreArm: Gyros not calibrated")
        proc._process(msg)
        assert state["prearm_ok"] is False
        assert "PreArm: Gyros not calibrated" in state["prearm_failures"]

    def test_ready_to_arm_clears_failures(self):
        proc, state, _ = _make_processor()
        # First set a failure
        proc._process(_mock_msg("STATUSTEXT", severity=3, text="PreArm: Gyros not calibrated"))
        assert state["prearm_ok"] is False
        # Then clear it
        proc._process(_mock_msg("STATUSTEXT", severity=6, text="Ready to arm"))
        assert state["prearm_ok"] is True
        assert state["prearm_failures"] == []

    def test_status_log_deduplicates(self):
        proc, state, _ = _make_processor()
        for _ in range(5):
            proc._process(_mock_msg("STATUSTEXT", severity=6, text="2M flash - use fmuv3 firmware"))
        assert state["status_log"].count("[INFO] 2M flash - use fmuv3 firmware") == 1

    def test_status_log_capped_at_10(self):
        proc, state, _ = _make_processor()
        for i in range(15):
            proc._process(_mock_msg("STATUSTEXT", severity=6, text=f"Message {i}"))
        assert len(state["status_log"]) <= 10


# ─── MqttPublisher._telemetry_payload tests ───────────────────────────────────

class TestTelemetryPayload:

    def _pub_with_state(self, state: dict) -> MqttPublisher:
        lock = threading.Lock()
        lock.acquire()
        lock.release()
        pub = MqttPublisher.__new__(MqttPublisher)
        pub.drone_id  = "HW-001"
        pub.state     = state
        pub.lock      = threading.Lock()
        pub._connected = True
        return pub

    def test_payload_has_required_keys(self):
        state = _empty_state()
        state.update({"latitude": 24.715, "longitude": 78.806, "altitude_m": 326.0,
                      "battery_pct": 94, "gps_fix": 3, "armed": False, "mode": "STABILIZE"})
        pub     = self._pub_with_state(state)
        payload = pub._telemetry_payload()

        required = ["drone_id", "source", "latitude", "longitude", "altitude_m",
                    "battery_pct", "gps_fix", "armed", "mode", "velocity_mps",
                    "heading_deg", "timestamp"]
        for key in required:
            assert key in payload, f"Missing key: {key}"

    def test_payload_drone_id(self):
        pub     = self._pub_with_state(_empty_state())
        payload = pub._telemetry_payload()
        assert payload["drone_id"] == "HW-001"

    def test_payload_source_is_edge_agent(self):
        pub     = self._pub_with_state(_empty_state())
        payload = pub._telemetry_payload()
        assert payload["source"] == "EDGE_AGENT"

    def test_payload_status_grounded(self):
        state = _empty_state()
        state["armed"]     = False
        state["prearm_ok"] = True
        pub     = self._pub_with_state(state)
        payload = pub._telemetry_payload()
        assert payload["status"] == "READY"

    def test_payload_status_grounded_not_ready(self):
        state = _empty_state()
        state["armed"]     = False
        state["prearm_ok"] = False
        pub     = self._pub_with_state(state)
        payload = pub._telemetry_payload()
        assert payload["status"] == "GROUNDED"

    def test_payload_status_active_when_armed(self):
        state = _empty_state()
        state["armed"]     = True
        state["prearm_ok"] = True
        pub     = self._pub_with_state(state)
        payload = pub._telemetry_payload()
        assert payload["status"] == "ACTIVE"

    def test_payload_has_timestamp(self):
        before  = time.time()
        pub     = self._pub_with_state(_empty_state())
        payload = pub._telemetry_payload()
        after   = time.time()
        assert before <= payload["timestamp"] <= after

    def test_payload_battery_pct_forwarded(self):
        state = _empty_state()
        state["battery_pct"] = 77
        pub     = self._pub_with_state(state)
        payload = pub._telemetry_payload()
        assert payload["battery_pct"] == 77
        assert payload["battery"] == 77       # backward-compat alias


class TestCommandExecution:

    def _command_pub(self, state: dict | None = None) -> MqttPublisher:
        pub = MqttPublisher.__new__(MqttPublisher)
        pub.drone_id = "HW-001"
        pub.state = state or _empty_state()
        pub.lock = threading.Lock()
        pub._connected = True
        pub.client = MagicMock()
        pub.processor = MagicMock()
        pub.processor.conn = MagicMock()
        pub.processor.conn.target_system = 1
        pub.processor.conn.target_component = 1
        pub.processor.conn.mav = MagicMock()
        return pub

    def test_arm_rejected_when_prearm_fails(self):
        state = _empty_state()
        state["prearm_ok"] = False
        pub = self._command_pub(state)

        ack = pub._execute_command({"cmd_id": "1", "command": "ARM", "drone_id": "HW-001"})

        assert ack["result"] == "FAILED"
        assert "prearm checks failed" in ack["detail"]
        pub.processor.conn.mav.command_long_send.assert_not_called()

    def test_force_arm_bypasses_prearm_gate(self):
        state = _empty_state()
        state["prearm_ok"] = False
        pub = self._command_pub(state)

        ack = pub._execute_command({"cmd_id": "2", "command": "FORCE_ARM", "drone_id": "HW-001"})

        assert ack["result"] == "OK"
        args = pub.processor.conn.mav.command_long_send.call_args.args
        assert args[4] == 1
        assert args[5] == FORCE_ARM_MAGIC

    def test_disarm_sends_zero_param(self):
        state = _empty_state()
        state["armed"] = True
        pub = self._command_pub(state)

        ack = pub._execute_command({"cmd_id": "3", "command": "DISARM", "drone_id": "HW-001"})

        assert ack["result"] == "OK"
        args = pub.processor.conn.mav.command_long_send.call_args.args
        assert args[4] == 0
        assert args[5] == 0

    def test_arm_with_force_param_normalizes_to_force_arm(self):
        pub = self._command_pub()

        assert pub._normalize_command({"command": "ARM", "params": {"force": True}}) == "FORCE_ARM"

    def test_handle_command_message_publishes_ack(self):
        pub = self._command_pub()

        pub._handle_command_message(b'{"cmd_id":"4","command":"ARM","drone_id":"HW-001"}')

        pub.client.publish.assert_called_once()


# ─── parse_ports_arg tests ────────────────────────────────────────────────────

class TestParsePortsArg:
    def test_port_with_drone_id(self):
        result = parse_ports_arg("COM6:HW-001")
        assert result == [("COM6", "HW-001")]

    def test_two_ports_with_ids(self):
        result = parse_ports_arg("COM6:HW-001,COM3:HW-002")
        assert result == [("COM6", "HW-001"), ("COM3", "HW-002")]

    def test_port_only_auto_ids(self):
        result = parse_ports_arg("COM6,COM3")
        assert result[0] == ("COM6", "HW-001")
        assert result[1] == ("COM3", "HW-002")

    def test_mixed_explicit_and_auto(self):
        result = parse_ports_arg("COM6:ALPHA,COM3")
        assert result[0] == ("COM6", "ALPHA")
        assert result[1] == ("COM3", "HW-002")

    def test_whitespace_stripped(self):
        result = parse_ports_arg(" COM6 : HW-001 , COM3 : HW-002 ")
        assert result[0] == ("COM6", "HW-001")
        assert result[1] == ("COM3", "HW-002")

    def test_single_port_no_colon(self):
        result = parse_ports_arg("COM6")
        assert result == [("COM6", "HW-001")]


# ─── DroneSession state isolation ────────────────────────────────────────────

class TestDroneSessionIsolation:
    def test_two_sessions_have_independent_states(self):
        """State mutations in session A must not affect session B."""
        s1 = DroneSession.__new__(DroneSession)
        s1.state = _empty_state()
        s1.lock  = threading.Lock()

        s2 = DroneSession.__new__(DroneSession)
        s2.state = _empty_state()
        s2.lock  = threading.Lock()

        s1.state["battery_pct"] = 80
        s1.state["drone_id"]    = "HW-001"

        assert s2.state["battery_pct"] == 0
        assert s2.state.get("drone_id") is None   # empty state has no drone_id

    def test_state_defaults_are_correct(self):
        s = DroneSession.__new__(DroneSession)
        s.state = _empty_state()
        assert s.state["armed"] is False
        assert s.state["prearm_ok"] is True
        assert s.state["msg_count"] == 0
        assert s.state["prearm_failures"] == []


# ─── Utility ─────────────────────────────────────────────────────────────────

class TestRadToDeg:
    def test_zero(self):
        import math
        assert _rad2deg(0.0) == 0.0

    def test_pi_is_180(self):
        import math
        assert abs(_rad2deg(math.pi) - 180.0) < 0.001

    def test_half_pi_is_90(self):
        import math
        assert abs(_rad2deg(math.pi / 2) - 90.0) < 0.001

    def test_negative(self):
        import math
        assert abs(_rad2deg(-math.pi) - (-180.0)) < 0.001
