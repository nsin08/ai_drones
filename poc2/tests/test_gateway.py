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
        MAV_CMD_NAV_WAYPOINT=16,
        MAV_FRAME_GLOBAL_RELATIVE_ALT_INT=6,
        MAV_MISSION_TYPE_MISSION=0,
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


class TestMissionExecution:

    def _mission_pub(self) -> MqttPublisher:
        pub = MqttPublisher.__new__(MqttPublisher)
        pub.drone_id = "HW-001"
        pub.state = _empty_state()
        pub.lock = threading.Lock()
        pub._connected = True
        pub.client = MagicMock()
        pub.processor = MagicMock()
        pub.processor.conn = MagicMock()
        pub.processor.conn.target_system = 1
        pub.processor.conn.target_component = 1
        pub.processor.conn.mav = MagicMock()
        pub.processor.upload_queue = None
        return pub

    def test_mission_rejected_without_waypoints(self):
        pub = self._mission_pub()

        ack = pub._execute_mission({"mission_id": "m1", "task_id": "t1", "drone_id": "HW-001", "waypoints": []})

        assert ack["result"] == "FAILED"
        assert "no waypoints" in ack["detail"]

    def test_mission_upload_sends_count_and_items(self):
        pub = self._mission_pub()

        class _MissionMsg:
            def __init__(self, msg_type, *, seq=None, ack_type=0):
                self._msg_type = msg_type
                self.seq = seq
                self.type = ack_type

            def get_type(self):
                return self._msg_type

        def _feed_upload_handshake():
            for _ in range(50):
                q = pub.processor.upload_queue
                if q is not None:
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=0))
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=1))
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=2))
                    q.put(_MissionMsg("MISSION_ACK", ack_type=0))
                    return
                time.sleep(0.01)

        feeder = threading.Thread(target=_feed_upload_handshake, daemon=True)
        feeder.start()

        def _count_send(*args, **kwargs):
            assert pub.processor.upload_queue is not None

        pub.processor.conn.mav.mission_count_send.side_effect = _count_send

        ack = pub._execute_mission({
            "mission_id": "m2",
            "task_id": "t2",
            "drone_id": "HW-001",
            "waypoints": [
                {"lat": 12.34, "lon": 56.78, "alt_m": 40, "cmd": 22},
                {"lat": 12.35, "lon": 56.79, "alt_m": 45, "cmd": 16},
            ],
        })

        assert ack["result"] == "OK"
        pub.processor.conn.mav.mission_count_send.assert_called_once()
        count_args = pub.processor.conn.mav.mission_count_send.call_args.args
        assert count_args[2] == 3
        assert pub.processor.conn.mav.mission_item_send.call_count == 3
        pub.processor.conn.mav.mission_set_current_send.assert_called_once_with(1, 1, 1)

    def test_mission_upload_ignores_clear_all_ack_before_requests(self):
        pub = self._mission_pub()

        class _MissionMsg:
            def __init__(self, msg_type, *, seq=None, ack_type=0):
                self._msg_type = msg_type
                self.seq = seq
                self.type = ack_type

            def get_type(self):
                return self._msg_type

        def _feed_clear_ack_then_upload():
            for _ in range(50):
                q = pub.processor.upload_queue
                if q is not None:
                    q.put(_MissionMsg("MISSION_ACK", ack_type=0))
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=0))
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=1))
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=2))
                    q.put(_MissionMsg("MISSION_ACK", ack_type=0))
                    return
                time.sleep(0.01)

        threading.Thread(target=_feed_clear_ack_then_upload, daemon=True).start()

        ack = pub._execute_mission({
            "mission_id": "m2b",
            "task_id": "t2b",
            "drone_id": "HW-001",
            "waypoints": [
                {"lat": 12.34, "lon": 56.78, "alt_m": 40, "cmd": 22},
                {"lat": 12.35, "lon": 56.79, "alt_m": 45, "cmd": 16},
            ],
        })

        assert ack["result"] == "OK"
        assert pub.processor.conn.mav.mission_item_send.call_count == 3

    def test_mission_upload_normalizes_takeoff_to_relative_alt_frame(self):
        pub = self._mission_pub()

        class _MissionMsg:
            def __init__(self, msg_type, *, seq=None, ack_type=0):
                self._msg_type = msg_type
                self.seq = seq
                self.type = ack_type

            def get_type(self):
                return self._msg_type

        def _feed_upload_takeoff_only():
            for _ in range(50):
                q = pub.processor.upload_queue
                if q is not None:
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=0))
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=1))
                    q.put(_MissionMsg("MISSION_ACK", ack_type=0))
                    return
                time.sleep(0.01)

        threading.Thread(target=_feed_upload_takeoff_only, daemon=True).start()

        ack = pub._execute_mission({
            "mission_id": "m2c",
            "task_id": "t2c",
            "drone_id": "HW-001",
            "waypoints": [
                {"lat": 12.34, "lon": 56.78, "alt_m": 10, "cmd": 22, "frame": 6},
            ],
        })

        assert ack["result"] == "OK"
        item_args = pub.processor.conn.mav.mission_item_send.call_args.args
        assert item_args[3] == 3
        assert item_args[4] == 22

    def test_mission_upload_fails_without_final_ack(self):
        pub = self._mission_pub()

        class _MissionMsg:
            def __init__(self, msg_type, *, seq=None, ack_type=0):
                self._msg_type = msg_type
                self.seq = seq
                self.type = ack_type

            def get_type(self):
                return self._msg_type

        def _feed_upload_requests_only():
            for _ in range(50):
                q = pub.processor.upload_queue
                if q is not None:
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=0))
                    q.put(_MissionMsg("MISSION_REQUEST_INT", seq=1))
                    return
                time.sleep(0.01)

        threading.Thread(target=_feed_upload_requests_only, daemon=True).start()

        ack = pub._execute_mission({
            "mission_id": "m4",
            "task_id": "t4",
            "drone_id": "HW-001",
            "waypoints": [
                {"lat": 12.34, "lon": 56.78, "alt_m": 40, "cmd": 22},
            ],
        })

        assert ack["result"] == "FAILED"
        assert "final ACK" in ack["detail"]

    def test_mission_upload_retries_with_legacy_clear_when_fc_stays_silent(self):
        pub = self._mission_pub()

        class _MissionMsg:
            def __init__(self, msg_type, *, seq=None, ack_type=0):
                self._msg_type = msg_type
                self.seq = seq
                self.type = ack_type

            def get_type(self):
                return self._msg_type

        send_counts = {"count": 0}

        def _count_send(*args, **kwargs):
            send_counts["count"] += 1
            if send_counts["count"] == 3:
                q = pub.processor.upload_queue
                assert q is not None
                q.put(_MissionMsg("MISSION_ACK", ack_type=0))
                q.put(_MissionMsg("MISSION_REQUEST_INT", seq=0))
                q.put(_MissionMsg("MISSION_REQUEST_INT", seq=1))
                q.put(_MissionMsg("MISSION_ACK", ack_type=0))

        pub.processor.conn.mav.mission_count_send.side_effect = _count_send

        ack = pub._execute_mission({
            "mission_id": "m4b",
            "task_id": "t4b",
            "drone_id": "HW-001",
            "waypoints": [
                {"lat": 12.34, "lon": 56.78, "alt_m": 40, "cmd": 22},
            ],
        })

        assert ack["result"] == "OK"
        assert send_counts["count"] >= 3
        pub.processor.conn.mav.mission_clear_all_send.assert_called_once()

    def test_mission_upload_requires_takeoff_as_first_runnable_item(self):
        pub = self._mission_pub()

        ack = pub._execute_mission({
            "mission_id": "m5",
            "task_id": "t5",
            "drone_id": "HW-001",
            "waypoints": [
                {"lat": 12.34, "lon": 56.78, "alt_m": 40, "cmd": 16},
            ],
        })

        assert ack["result"] == "FAILED"
        assert "MAV_CMD_NAV_TAKEOFF" in ack["detail"]

    def test_handle_mission_message_publishes_ack(self):
        pub = self._mission_pub()

        pub._handle_mission_message(
            b'{"mission_id":"m3","task_id":"t3","drone_id":"HW-001","waypoints":[{"lat":1,"lon":2,"alt_m":3}]}'
        )

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


# ─── RC channel override (throttle-nudge elimination) ─────────────────────────

class TestAutoArmRcOverride:
    """
    Verify that _auto_arm_and_start() sends rc_channels_override_send with
    throttle neutral (1000 PWM, chan3) before switching to AUTO mode.

    This eliminates the need for a physical RC throttle nudge after upload.
    ArduPilot requires a live throttle signal before accepting a MAVLink-
    armed AUTO takeoff; the override satisfies that check in software.
    """

    def _make_publisher(self, *, armed: bool = True):
        """Return an MqttPublisher with mocked MAVLink connection and MQTT client."""
        state = _empty_state()
        state["armed"] = armed  # pre-set so arm-confirmation loop exits immediately
        lock = threading.Lock()

        mock_conn = MagicMock()
        mock_proc = MagicMock()
        mock_proc.conn = mock_conn

        pub = MqttPublisher.__new__(MqttPublisher)
        pub.state = state
        pub.lock = lock
        pub.drone_id = "HW-001"
        pub.processor = mock_proc
        pub._status_log = []
        pub._append_status_log = lambda msg: pub._status_log.append(msg)
        pub._wait_for_mode = MagicMock(return_value=True)
        pub._trace_takeoff_window = MagicMock()  # don't spin a real trace thread

        return pub, mock_conn

    def test_rc_override_sent_before_auto(self):
        """rc_channels_override_send must be called before set_mode('AUTO')."""
        pub, mock_conn = self._make_publisher(armed=True)
        call_order = []
        mock_conn.mav.rc_channels_override_send.side_effect = (
            lambda *a, **kw: call_order.append("rc_override")
        )
        mock_conn.set_mode.side_effect = lambda m: call_order.append(f"set_mode:{m}")

        with patch("time.sleep"):
            pub._auto_arm_and_start()

        assert "rc_override" in call_order, "rc_channels_override_send was never called"
        assert "set_mode:AUTO" in call_order, "set_mode(AUTO) was never called"
        rc_idx = call_order.index("rc_override")
        auto_idx = call_order.index("set_mode:AUTO")
        assert rc_idx < auto_idx, "rc_override must be sent before set_mode(AUTO)"

    def test_rc_override_throttle_channel_is_neutral(self):
        """Throttle channel (chan3, positional index 4) must be 1000 (neutral)."""
        pub, mock_conn = self._make_publisher(armed=True)

        with patch("time.sleep"):
            pub._auto_arm_and_start()

        mock_conn.mav.rc_channels_override_send.assert_called_once()
        args = mock_conn.mav.rc_channels_override_send.call_args[0]
        # (target_system, target_component, chan1, chan2, chan3, chan4, chan5, chan6, chan7, chan8)
        #  index 0         index 1           idx2   idx3  idx4  ...
        assert len(args) >= 5, "Expected ≥5 positional args"
        throttle_val = args[4]  # chan3 is index 4
        assert throttle_val == 1000, (
            f"Throttle override must be 1000 (neutral), got {throttle_val}"
        )

    def test_rc_override_other_channels_are_passthrough(self):
        """All non-throttle channels must be 0 (pass-through, not overriding RC)."""
        pub, mock_conn = self._make_publisher(armed=True)

        with patch("time.sleep"):
            pub._auto_arm_and_start()

        args = mock_conn.mav.rc_channels_override_send.call_args[0]
        # args: (sys, comp, ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8)
        # skip ch3 at index 4
        passthrough = list(args[2:4]) + list(args[5:])
        for i, val in enumerate(passthrough):
            assert val == 0, (
                f"Non-throttle channel at result-index {i} must be 0, got {val}"
            )

    def test_auto_arm_aborts_if_arm_not_confirmed(self):
        """If arm is not confirmed within timeout, AUTO and RC override must not fire."""
        pub, mock_conn = self._make_publisher(armed=False)  # never goes armed

        with patch("time.sleep"):
            pub._auto_arm_and_start()

        mode_calls = [c[0][0] for c in mock_conn.set_mode.call_args_list]
        assert "AUTO" not in mode_calls, "AUTO must not be set if arm not confirmed"
        mock_conn.mav.rc_channels_override_send.assert_not_called()
