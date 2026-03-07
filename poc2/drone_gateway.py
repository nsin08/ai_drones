#!/usr/bin/env python3
"""
poc2/drone_gateway.py
─────────────────────
MAVLink → MQTT bridge for a single real ArduPilot drone.

Reads live telemetry from the flight controller via MAVLink and
publishes it to the existing AIP MQTT topics so the drone appears
in the React Mission Control UI without any changes to the backend.

MQTT topics published:
  fleet/<droneId>/telemetry   ← main telemetry (1 Hz, configurable)
  fleet/<droneId>/status      ← prearm / vehicle health summary

Topic schema matches swarmsim.py so mission_control_v3.py picks it
up with zero modification.  DroneID uses the "HW-" prefix which maps
to source="EDGE_AGENT" in the UI.

Supports ARM / DISARM / FORCE_ARM command ingress via MQTT.

Usage:
    python drone_gateway.py
    python drone_gateway.py --port COM6 --baud 57600 --drone-id HW-001
    python drone_gateway.py --port COM6 --broker 192.168.1.100 --hz 5

Requirements:
    pip install pymavlink pyserial paho-mqtt
    Close Mission Planner before running (port conflict).
    MQTT broker running (default: localhost:1883)
"""

import argparse
import json
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

try:
    from pymavlink import mavutil
except ImportError:
    sys.exit("❌  pymavlink not installed.  Run:  pip install pymavlink pyserial")

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("❌  paho-mqtt not installed.  Run:  pip install paho-mqtt")


# ─── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_DRONE_ID   = "HW-001"
DEFAULT_BAUD       = 57600
DEFAULT_BROKER     = "localhost"
DEFAULT_PORT_NUM   = 1883
DEFAULT_HZ         = 1          # publish rate (1 Hz matches swarmsim default)
HEARTBEAT_TIMEOUT  = 15
FORCE_ARM_MAGIC    = 21196
AUTO_PORTS         = ["COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
                      "COM9", "COM10", "COM11", "COM12"]
AUTO_BAUDS         = [57600, 115200]
SEV_NAMES          = {0: "EMERGENCY", 1: "ALERT", 2: "CRITICAL",
                      3: "ERROR", 4: "WARNING", 5: "NOTICE",
                      6: "INFO", 7: "DEBUG"}
SUPPORTED_COMMANDS = {"ARM", "DISARM", "FORCE_ARM"}
COMMAND_ACK_TOPIC  = "fleet/system/command_ack"
MISSION_ACK_TOPIC  = "fleet/system/mission_ack"
RUN_LOG_STAMP      = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_LOG_PATH       = Path(__file__).resolve().parent / "run_logs" / f"drone_gateway_{RUN_LOG_STAMP}.log"


# ─── Shared telemetry state ────────────────────────────────────────────────────

def _empty_state():
    return {
        "armed": False,
        "mode": "STABILIZE",
        "vehicle_type": "QUADROTOR",
        # position
        "latitude": None,
        "longitude": None,
        "altitude_m": None,
        "relative_alt_m": None,
        # motion
        "velocity_mps": 0.0,
        "speed_mps": 0.0,
        "heading_deg": 0.0,
        # battery
        "battery_pct": 0,
        "voltage_v": None,
        "current_a": None,
        # gps
        "gps_fix": 0,
        "satellites_visible": 0,
        "hdop": None,
        # attitude
        "roll_deg": 0.0,
        "pitch_deg": 0.0,
        "yaw_deg": 0.0,
        # health
        "ekf_ok": False,
        "ekf_flags": 0,
        "vibe_x": 0.0,
        "vibe_y": 0.0,
        "vibe_z": 0.0,
        # status
        "prearm_ok": True,
        "prearm_failures": [],
        "status_log": [],        # last 10 STATUSTEXT entries
        # meta
        "msg_count": 0,
        "last_heartbeat": None,
        "mission_current_seq": None,
        "last_item_reached": None,
        "enable_run_log": False,
    }


def _rad2deg(r):
    import math
    return r * 180.0 / math.pi


def _record_status_entry(state, entry, *, drone_id=None):
    log = state["status_log"]
    if entry in log:
        return

    log.insert(0, entry)
    state["status_log"] = log[:10]

    if not state.get("enable_run_log"):
        return

    try:
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"{stamp} [{drone_id or 'UNKNOWN'}]"
        with RUN_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"{prefix} {entry}\n")
    except Exception:
        pass


# ─── MAVLink message processor ────────────────────────────────────────────────

class MavlinkProcessor:
    """Owns the MAVLink connection and updates the shared state dict."""

    def __init__(self, port, baud, state: dict, lock: threading.Lock, drone_id=None):
        self.port  = port
        self.baud  = baud
        self.state = state
        self.lock  = lock
        self.drone_id = drone_id
        self.conn  = None
        # Set by _upload_waypoints to intercept mission handshake messages
        # from the receiver loop so both threads don't race on recv_match.
        self.upload_queue = None

    def connect(self) -> bool:
        ports = [self.port] if self.port else AUTO_PORTS
        bauds = [self.baud] if self.port else AUTO_BAUDS
        for p in ports:
            for b in bauds:
                try:
                    print(f"  Trying {p} @ {b}...")
                    c = mavutil.mavlink_connection(p, baud=b)
                    hb = c.wait_heartbeat(timeout=5)
                    if hb:
                        self.conn = c
                        self.port = p
                        self.baud = b
                        print(f"  ✅  Heartbeat  sysid={c.target_system}  compid={c.target_component}  port={p}  baud={b}")
                        # Request all streams at 4 Hz
                        c.mav.request_data_stream_send(
                            c.target_system, c.target_component,
                            mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
                        return True
                    c.close()
                except Exception as e:
                    print(f"    {p}@{b}: {e}")
        return False

    def run_forever(self):
        """Blocking receive loop — run in a thread."""
        while True:
            try:
                msg = self.conn.recv_match(blocking=True, timeout=1.0)
                if msg and msg.get_type() != "BAD_DATA":
                    self._process(msg)
            except Exception as e:
                print(f"  MAVLink recv error: {e}")
                time.sleep(1)

    def _process(self, msg):
        t = msg.get_type()
        with self.lock:
            s = self.state
            s["msg_count"] += 1

            if t == "HEARTBEAT":
                prev_mode = s["mode"]
                prev_armed = s["armed"]
                s["mode"]    = mavutil.mode_string_v10(msg)
                s["armed"]   = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                vt = msg.type
                s["vehicle_type"] = mavutil.mavlink.enums["MAV_TYPE"].get(
                    vt, type("x", (), {"name": str(vt)})()).name.replace("MAV_TYPE_", "")
                s["last_heartbeat"] = time.time()
                if prev_mode != s["mode"] or prev_armed != s["armed"]:
                    entry = f"[DEBUG] HEARTBEAT mode={s['mode']} armed={s['armed']}"
                    _record_status_entry(s, entry, drone_id=getattr(self, "drone_id", None))

            elif t == "ATTITUDE":
                s["roll_deg"]    = round(_rad2deg(msg.roll), 2)
                s["pitch_deg"]   = round(_rad2deg(msg.pitch), 2)
                s["yaw_deg"]     = round(_rad2deg(msg.yaw), 2)
                s["heading_deg"] = round(_rad2deg(msg.yaw) % 360, 1)

            elif t == "GPS_RAW_INT":
                s["gps_fix"]           = msg.fix_type
                s["satellites_visible"] = msg.satellites_visible
                s["hdop"]              = msg.eph / 100.0 if msg.eph else None
                if msg.lat != 0:
                    s["latitude"]  = round(msg.lat / 1e7, 7)
                    s["longitude"] = round(msg.lon / 1e7, 7)

            elif t == "SYS_STATUS":
                s["battery_pct"] = msg.battery_remaining
                s["voltage_v"]   = round(msg.voltage_battery / 1000.0, 2)
                s["current_a"]   = round(msg.current_battery / 100.0, 2)

            elif t == "VFR_HUD":
                s["altitude_m"]  = round(msg.alt, 1)
                s["velocity_mps"] = round(msg.groundspeed, 2)
                s["speed_mps"]   = round(msg.groundspeed, 2)
                s["heading_deg"] = round(msg.heading, 1)

            elif t == "GLOBAL_POSITION_INT":
                if getattr(msg, "relative_alt", None) is not None:
                    s["relative_alt_m"] = round(msg.relative_alt / 1000.0, 1)

            elif t == "EKF_STATUS_REPORT":
                s["ekf_flags"] = msg.flags
                s["ekf_ok"]    = bool(msg.flags & 0x01)

            elif t == "VIBRATION":
                s["vibe_x"] = round(msg.vibration_x, 2)
                s["vibe_y"] = round(msg.vibration_y, 2)
                s["vibe_z"] = round(msg.vibration_z, 2)

            elif t == "COMMAND_ACK":
                entry = f"[DEBUG] COMMAND_ACK cmd={msg.command} result={msg.result}"
                _record_status_entry(s, entry, drone_id=getattr(self, "drone_id", None))

            elif t == "MISSION_CURRENT":
                if s.get("mission_current_seq") != msg.seq:
                    s["mission_current_seq"] = msg.seq
                    entry = f"[DEBUG] MISSION_CURRENT seq={msg.seq}"
                    _record_status_entry(s, entry, drone_id=getattr(self, "drone_id", None))

            elif t == "MISSION_ITEM_REACHED":
                if s.get("last_item_reached") != msg.seq:
                    s["last_item_reached"] = msg.seq
                    entry = f"[DEBUG] MISSION_REACHED seq={msg.seq}"
                    _record_status_entry(s, entry, drone_id=getattr(self, "drone_id", None))

            elif t in ("MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"):
                # During upload, hand these off to the uploader thread via the
                # queue so we don't compete on conn.recv_match.
                q = self.upload_queue
                if q is not None:
                    try:
                        q.put_nowait(msg)
                    except Exception:
                        pass
                # fall through — also count the message

            elif t == "STATUSTEXT":
                text     = msg.text.strip()
                sev_name = SEV_NAMES.get(msg.severity, str(msg.severity))
                entry    = f"[{sev_name}] {text}"
                _record_status_entry(s, entry, drone_id=getattr(self, "drone_id", None))

                if "PreArm" in text or "prearm" in text.lower():
                    s["prearm_ok"] = False
                    if text not in s["prearm_failures"]:
                        s["prearm_failures"].append(text)
                if "Ready to arm" in text or "PreArm checks passed" in text:
                    s["prearm_ok"]       = True
                    s["prearm_failures"] = []


# ─── MQTT Publisher ───────────────────────────────────────────────────────────

class MqttPublisher:
    """Publishes telemetry snapshots to the AIP MQTT topics."""

    def __init__(self, broker, port, drone_id, hz, state, lock, processor):
        self.broker   = broker
        self.port     = port
        self.drone_id = drone_id
        self.hz       = hz
        self.state    = state
        self.lock     = lock
        self.processor = processor
        self.client   = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message
        self._connected = False

    def _on_connect(self, client, userdata, flags, reason_code, props=None):
        rc = reason_code if isinstance(reason_code, int) else reason_code.value
        if rc == 0:
            self._connected = True
            client.subscribe(self._command_topic())
            client.subscribe(self._mission_topic())
            print(f"  ✅  MQTT connected  broker={self.broker}:{self.port}")
        else:
            print(f"  ❌  MQTT connect failed  rc={rc}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, props=None):
        self._connected = False
        print(f"  ⚠️   MQTT disconnected (rc={reason_code}), reconnecting...")

    def _on_message(self, client, userdata, msg):
        if msg.topic == self._command_topic():
            self._handle_command_message(msg.payload)
            return
        if msg.topic == self._mission_topic():
            self._handle_mission_message(msg.payload)

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            # Wait up to 5s for connection
            for _ in range(50):
                if self._connected:
                    return True
                time.sleep(0.1)
            return self._connected
        except Exception as e:
            print(f"  ❌  MQTT broker unreachable at {self.broker}:{self.port}: {e}")
            return False

    def _command_topic(self):
        return f"fleet/{self.drone_id}/command"

    def _mission_topic(self):
        return f"fleet/{self.drone_id}/mission"

    def _handle_command_message(self, raw_payload):
        try:
            payload = json.loads(raw_payload.decode() if isinstance(raw_payload, bytes) else raw_payload)
        except Exception as e:
            self._publish_command_ack({
                "cmd_id": None,
                "drone_id": self.drone_id,
                "command": "UNKNOWN",
                "result": "FAILED",
                "detail": f"invalid JSON payload: {e}",
                "timestamp": time.time(),
            })
            return

        ack = self._execute_command(payload)
        self._publish_command_ack(ack)

    def _execute_command(self, payload):
        command = self._normalize_command(payload)
        cmd_id = payload.get("cmd_id")
        payload_drone_id = payload.get("drone_id")

        if payload_drone_id and payload_drone_id != self.drone_id:
            return self._ack_payload(
                cmd_id=cmd_id,
                command=command or "UNKNOWN",
                result="FAILED",
                detail=f"wrong target drone_id={payload_drone_id}",
            )

        if command not in SUPPORTED_COMMANDS:
            return self._ack_payload(
                cmd_id=cmd_id,
                command=command or "UNKNOWN",
                result="FAILED",
                detail=f"unsupported command: {command}",
            )

        force = command == "FORCE_ARM"
        arm = command in {"ARM", "FORCE_ARM"}

        with self.lock:
            current_armed = bool(self.state["armed"])
            prearm_ok = bool(self.state["prearm_ok"])

        if arm and current_armed:
            return self._ack_payload(cmd_id=cmd_id, command=command, result="OK", detail="already armed")
        if (not arm) and (not current_armed):
            return self._ack_payload(cmd_id=cmd_id, command=command, result="OK", detail="already disarmed")
        if arm and (not force) and (not prearm_ok):
            return self._ack_payload(
                cmd_id=cmd_id,
                command=command,
                result="FAILED",
                detail="prearm checks failed; use FORCE_ARM only if you accept the risk",
            )

        try:
            self._send_arm_disarm(arm=arm, force=force)
            detail = "force arm command sent" if force else f"{command.lower()} command sent"
            self._append_status_log(f"[NOTICE] MQTT command {command} accepted")
            return self._ack_payload(cmd_id=cmd_id, command=command, result="OK", detail=detail)
        except Exception as e:
            self._append_status_log(f"[ERROR] MQTT command {command} failed: {e}")
            return self._ack_payload(cmd_id=cmd_id, command=command, result="FAILED", detail=str(e))

    @staticmethod
    def _normalize_command(payload):
        command = str(payload.get("command") or "").strip().upper()
        params = payload.get("params") or {}
        if command == "ARM" and params.get("force"):
            return "FORCE_ARM"
        return command

    def _wait_for_mode(self, conn, target_mode, timeout_s=3.0):
        """Spin until heartbeat confirms the mode, or timeout."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(0.1)
            with self.lock:
                if self.state.get("mode", "").upper() == target_mode.upper():
                    return True
        return False

    def _snapshot_state(self):
        with self.lock:
            return dict(self.state)

    def _send_arm_disarm(self, *, arm, force):
        conn = self.processor.conn
        if conn is None:
            raise RuntimeError("MAVLink connection not ready")

        if arm:
            # ArduCopter hard rule: AUTO / GUIDED are NOT directly armable.
            # Required GCS sequence:
            #   1. STABILIZE  → arm (motors idle)
            #   2. AUTO       → mission begins executing
            with self.lock:
                current_mode = self.state.get("mode", "")

            if current_mode.upper() != "STABILIZE":
                try:
                    conn.set_mode("STABILIZE")
                    if self._wait_for_mode(conn, "STABILIZE", 3.0):
                        self._append_status_log("[NOTICE] STABILIZE mode confirmed — sending ARM")
                    else:
                        self._append_status_log("[WARN] STABILIZE mode not confirmed, trying ARM anyway")
                except Exception as e:
                    self._append_status_log(f"[WARN] STABILIZE switch failed: {e}")

        # Normal ARM obeys pre-arm checks. FORCE_ARM explicitly bypasses them.
        param1 = 1 if arm else 0
        param2 = FORCE_ARM_MAGIC if (arm and force) else 0
        conn.mav.command_long_send(
            conn.target_system,
            conn.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            param1,
            param2,
            0,
            0,
            0,
            0,
            0,
        )

        if arm:
            # Wait for armed confirmation, then switch to AUTO
            self._append_status_log("[NOTICE] Waiting for arm confirmation...")
            armed_confirmed = False
            for _ in range(30):  # up to 3 s
                time.sleep(0.1)
                with self.lock:
                    if self.state.get("armed", False):
                        armed_confirmed = True
                        break

            if armed_confirmed:
                try:
                    conn.set_mode("AUTO")
                    if self._wait_for_mode(conn, "AUTO", 3.0):
                        self._append_status_log("[NOTICE] AUTO mode active — mission executing")
                    else:
                        self._append_status_log("[WARN] AUTO mode not confirmed after arm")
                except Exception as e:
                    self._append_status_log(f"[WARN] AUTO switch after arm failed: {e}")
            else:
                self._append_status_log("[WARN] Arm not confirmed within 3s — AUTO not switched")

    def _publish_command_ack(self, payload):
        if not self._connected:
            return
        self.client.publish(COMMAND_ACK_TOPIC, json.dumps(payload))

    def _handle_mission_message(self, raw_payload):
        try:
            payload = json.loads(raw_payload.decode() if isinstance(raw_payload, bytes) else raw_payload)
        except Exception as e:
            self._publish_mission_ack({
                "mission_id": None,
                "task_id": None,
                "drone_id": self.drone_id,
                "result": "FAILED",
                "detail": f"invalid JSON payload: {e}",
                "timestamp": time.time(),
            })
            return

        ack = self._execute_mission(payload)
        self._publish_mission_ack(ack)

    def _execute_mission(self, payload):
        mission_id = payload.get("mission_id")
        task_id = payload.get("task_id")
        payload_drone_id = payload.get("drone_id")
        action = str(payload.get("action") or "UPLOAD").strip().upper()
        waypoints = payload.get("waypoints") or []

        if payload_drone_id and payload_drone_id != self.drone_id:
            return self._mission_ack_payload(
                mission_id=mission_id,
                task_id=task_id,
                result="FAILED",
                detail=f"wrong target drone_id={payload_drone_id}",
            )

        if action != "UPLOAD":
            return self._mission_ack_payload(
                mission_id=mission_id,
                task_id=task_id,
                result="FAILED",
                detail=f"unsupported mission action: {action}",
            )

        if not isinstance(waypoints, list) or not waypoints:
            return self._mission_ack_payload(
                mission_id=mission_id,
                task_id=task_id,
                result="FAILED",
                detail="no waypoints supplied",
            )

        try:
            self._upload_waypoints(waypoints)
            self._append_status_log(
                f"[NOTICE] Mission upload accepted ({len(waypoints)} waypoints)"
            )
            # Auto-execute: switch AUTO (disarmed) → arm → mission starts.
            # Runs in a background thread so MQTT ack is returned immediately.
            threading.Thread(target=self._auto_arm_and_start, daemon=True).start()
            return self._mission_ack_payload(
                mission_id=mission_id,
                task_id=task_id,
                result="OK",
                detail=f"uploaded {len(waypoints)} waypoints, arming...",
            )
        except Exception as e:
            self._append_status_log(f"[ERROR] Mission upload failed: {e}")
            return self._mission_ack_payload(
                mission_id=mission_id,
                task_id=task_id,
                result="FAILED",
                detail=str(e),
            )

    def _auto_arm_and_start(self):
        """
        Runs in background after a successful upload.
        ArduCopter hard rule: MAVLink arming is ONLY accepted in STABILIZE/ACRO.
        Sequence: STABILIZE → arm → AUTO.
        The uploaded mission includes HOME at seq 0 and TAKEOFF at seq 1.
        """
        conn = self.processor.conn
        if conn is None:
            return

        time.sleep(0.5)  # let FC digest mission_set_current

        # 1. STABILIZE — the only mode that accepts MAVLink arm
        try:
            conn.set_mode("STABILIZE")
            self._append_status_log("[NOTICE] Switching to STABILIZE for arm")
        except Exception as e:
            self._append_status_log(f"[WARN] STABILIZE switch failed: {e}")
            return

        if not self._wait_for_mode(conn, "STABILIZE", 4.0):
            self._append_status_log("[WARN] STABILIZE not confirmed — aborting auto-arm")
            return

        time.sleep(0.3)

        # 2. Arm with force magic (bypasses sensor checks; pre-arm is already CLEAR)
        self._append_status_log("[NOTICE] STABILIZE confirmed — sending ARM")
        conn.mav.command_long_send(
            conn.target_system,
            conn.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, FORCE_ARM_MAGIC, 0, 0, 0, 0, 0,
        )

        # 3. Wait for armed confirmation
        armed = False
        for _ in range(40):  # up to 4 s
            time.sleep(0.1)
            with self.lock:
                if self.state.get("armed", False):
                    armed = True
                    break

        if not armed:
            self._append_status_log("[WARN] Arm not confirmed within 4s")
            return

        self._append_status_log("[NOTICE] Armed in STABILIZE — sending RC throttle neutral override")
        time.sleep(0.2)

        # 4a. RC_CHANNELS_OVERRIDE — throttle neutral (1000 PWM, chan3).
        #     ArduPilot requires a live RC throttle signal before accepting an
        #     autonomous takeoff, even when armed by GCS MAVLink.  Sending a
        #     single override frame satisfies the check without physical RC input.
        #     Channel values:
        #       0 = pass-through (ignore; FC uses real RC value)
        #       1000 = explicit neutral/minimum for throttle
        #     We set chan3=1000, all others=0 (pass-through), then let the
        #     override expire naturally once AUTO mode activates (≤1 s).
        try:
            conn.mav.rc_channels_override_send(
                conn.target_system,
                conn.target_component,
                0,     # chan1  roll    — pass-through
                0,     # chan2  pitch   — pass-through
                1000,  # chan3  throttle — neutral
                0,     # chan4  yaw     — pass-through
                0,     # chan5
                0,     # chan6
                0,     # chan7
                0,     # chan8
            )
            self._append_status_log("[NOTICE] RC throttle override sent (neutral) — switching to AUTO")
        except Exception as e:
            self._append_status_log(f"[WARN] RC override send failed: {e} — proceeding anyway")

        time.sleep(0.15)  # brief settle before mode switch

        # 4b. Switch to AUTO — now that we're armed and the mission pointer
        #     targets seq 1 (the TAKEOFF), the mission can begin.
        try:
            conn.set_mode("AUTO")
        except Exception as e:
            self._append_status_log(f"[WARN] AUTO switch failed: {e}")
            return

        if self._wait_for_mode(conn, "AUTO", 4.0):
            self._append_status_log("[NOTICE] AUTO active — mission executing")
            threading.Thread(target=self._trace_takeoff_window, daemon=True).start()
        else:
            self._append_status_log("[WARN] AUTO not confirmed after arm")

    def _trace_takeoff_window(self):
        """Trace the first few seconds after AUTO engages."""
        start = self._snapshot_state()
        start_alt = start.get("altitude_m")
        start_rel_alt = start.get("relative_alt_m")
        start_mode = start.get("mode")
        start_armed = start.get("armed")
        start_speed = start.get("speed_mps")
        self._append_status_log(
            f"[DEBUG] Takeoff trace start mode={start_mode} armed={start_armed} relAlt={start_rel_alt} alt={start_alt} spd={start_speed}"
        )

        checkpoints = (0.5, 1.0, 2.0, 4.0, 8.0)
        base = time.time()
        prev_mode = start_mode
        prev_armed = start_armed
        for delay in checkpoints:
            sleep_for = base + delay - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            snap = self._snapshot_state()
            alt = snap.get("altitude_m")
            rel_alt = snap.get("relative_alt_m")
            delta = None
            if start_rel_alt is not None and rel_alt is not None:
                delta = round(rel_alt - start_rel_alt, 1)
            elif start_alt is not None and alt is not None:
                delta = round(alt - start_alt, 1)
            mode = snap.get("mode")
            armed = snap.get("armed")
            speed = snap.get("speed_mps")
            amps = snap.get("current_a")
            transition = ""
            if mode != prev_mode or armed != prev_armed:
                transition = " state-change"
            prev_mode = mode
            prev_armed = armed
            self._append_status_log(
                f"[DEBUG] T+{delay:0.1f}s mode={mode} armed={armed} relAlt={rel_alt} dRel={delta} alt={alt} spd={speed} amps={amps}{transition}"
            )

    def _upload_waypoints(self, waypoints):
        conn = self.processor.conn
        if conn is None:
            raise RuntimeError("MAVLink connection not ready")

        mav = conn.mav
        ts = conn.target_system
        tc = conn.target_component
        mission_type  = getattr(mavutil.mavlink, "MAV_MISSION_TYPE_MISSION", 0)
        default_frame = getattr(mavutil.mavlink, "MAV_FRAME_GLOBAL_RELATIVE_ALT", 3)
        default_cmd   = getattr(mavutil.mavlink, "MAV_CMD_NAV_WAYPOINT", 16)

        item_int_send = getattr(mav, "mission_item_int_send", None)
        item_send     = getattr(mav, "mission_item_send", None)

        takeoff_cmd = getattr(mavutil.mavlink, "MAV_CMD_NAV_TAKEOFF", 22)
        mission_frame = getattr(mavutil.mavlink, "MAV_FRAME_GLOBAL_RELATIVE_ALT", 3)
        frame_mission = getattr(mavutil.mavlink, "MAV_FRAME_MISSION", 2)

        # ArduPilot Copter expects a HOME placeholder at seq 0 and the first
        # runnable mission command (TAKEOFF) at seq 1.
        first_cmd = int((waypoints[0] or {}).get("cmd", (waypoints[0] or {}).get("command", -1)))
        if first_cmd != takeoff_cmd:
            raise RuntimeError("Mission must start with MAV_CMD_NAV_TAKEOFF (22) as the first runnable item")

        with self.lock:
            home_lat = self.state.get("latitude")
            home_lon = self.state.get("longitude")

        if home_lat is None:
            home_lat = float((waypoints[0] or {}).get("lat", (waypoints[0] or {}).get("latitude", 0.0)))
        if home_lon is None:
            home_lon = float((waypoints[0] or {}).get(
                "lon",
                (waypoints[0] or {}).get("longitude", (waypoints[0] or {}).get("lng", 0.0)),
            ))

        home_item = {
            "cmd": getattr(mavutil.mavlink, "MAV_CMD_NAV_WAYPOINT", 16),
            "frame": mission_frame,
            "lat": home_lat,
            "lon": home_lon,
            "alt_m": 0.0,
            "param1": 0.0,
            "param2": 0.0,
            "param3": 0.0,
            "param4": 0.0,
        }
        full_items = [home_item] + list(waypoints)
        self._append_status_log(
            f"[DEBUG] Mission upload prepared items={len(full_items)} takeoff_seq=1 current_seq=1 first_cmd={first_cmd}"
        )

        def _send_item(seq, wp):
            lat = float(wp.get("lat", wp.get("latitude", 0.0)))
            lon = float(wp.get("lon", wp.get("longitude", wp.get("lng", 0.0))))
            alt = float(wp.get("alt_m", wp.get("altitude_m", wp.get("alt", 0.0))))
            wp_cmd   = int(wp.get("cmd",   wp.get("command", default_cmd)))
            wp_frame = int(wp.get("frame", default_frame))
            p1 = float(wp.get("param1", 0.0))
            p2 = float(wp.get("param2", 0.0))
            p3 = float(wp.get("param3", 0.0))
            p4 = float(wp.get("param4", 0.0))
            # Keep all uploaded items non-current; MISSION_SET_CURRENT selects
            # the runnable start point after upload.
            current = 0

            # ArduPilot mission docs expect standard mission frames, not the
            # *_INT frame variants the UI may send.
            if wp_cmd in {
                getattr(mavutil.mavlink, "MAV_CMD_NAV_WAYPOINT", 16),
                getattr(mavutil.mavlink, "MAV_CMD_NAV_LOITER_TIME", 19),
                getattr(mavutil.mavlink, "MAV_CMD_NAV_TAKEOFF", 22),
            }:
                wp_frame = mission_frame
            elif wp_cmd in {
                getattr(mavutil.mavlink, "MAV_CMD_NAV_RETURN_TO_LAUNCH", 20),
                getattr(mavutil.mavlink, "MAV_CMD_CONDITION_YAW", 115),
            }:
                wp_frame = frame_mission
            elif wp_frame == 6:
                wp_frame = mission_frame

            self._append_status_log(
                f"[DEBUG] Send seq={seq} cmd={wp_cmd} frame={wp_frame} current={current} alt={alt}"
            )

            if callable(item_send):
                item_send(ts, tc, seq, wp_frame, wp_cmd,
                          current, 1, p1, p2, p3, p4, lat, lon, alt)
                return

            if callable(item_int_send):
                x = int(round(lat * 1e7))
                y = int(round(lon * 1e7))
                item_int_send(ts, tc, seq, wp_frame, wp_cmd,
                              current, 1, p1, p2, p3, p4, x, y, alt)
                return

            raise RuntimeError("No MISSION_ITEM sender available")

        total = len(full_items)

        # ── 1. Send item count ───────────────────────────────────────────────
        # Older fmuv3 builds can emit an immediate MISSION_ACK after
        # MISSION_CLEAR_ALL; avoid that handshake ambiguity and let
        # MISSION_COUNT start the replacement upload directly.
        count_send = getattr(mav, "mission_count_send", None)
        clear_all = getattr(mav, "mission_clear_all_send", None)
        if not callable(count_send):
            raise RuntimeError("MISSION_COUNT sender unavailable")
        # Install the upload queue before MISSION_COUNT so an immediate
        # MISSION_REQUEST(_INT) from the FC is not lost by the receiver thread.
        import queue as _queue
        q = _queue.Queue()
        self.processor.upload_queue = q
        try:
            count_send(ts, tc, total)
        except TypeError:
            count_send(ts, tc, total, mission_type)

        # ── 2. Handshake via queue (avoids race with the receiver thread) ──
        # The MavlinkProcessor._process() routes MISSION_REQUEST/ACK here.
        remaining = set(range(total))
        deadline  = time.time() + 30
        upload_ok = False
        last_resend = time.time()
        ack_deadline = None
        request_seen = False
        ignored_clear_ack = False
        silent_retries = 0
        legacy_restart_attempted = False

        try:
            while time.time() < deadline and not upload_ok:
                try:
                    msg = q.get(timeout=0.5 if not remaining else 2)
                except _queue.Empty:
                    # FC silent for 2 s — resend count to re-trigger requests
                    if remaining and time.time() - last_resend >= 2:
                        if not request_seen:
                            silent_retries += 1
                        if (
                            not request_seen
                            and silent_retries >= 2
                            and not legacy_restart_attempted
                            and callable(clear_all)
                        ):
                            self._append_status_log(
                                "[DEBUG] No mission requests; trying legacy clear+count restart"
                            )
                            try:
                                clear_all(ts, tc)
                            except TypeError:
                                clear_all(ts, tc, mission_type)
                            time.sleep(0.1)
                            ignored_clear_ack = False
                            legacy_restart_attempted = True
                        try:
                            count_send(ts, tc, total)
                        except TypeError:
                            count_send(ts, tc, total, mission_type)
                        last_resend = time.time()
                    elif ack_deadline is not None and time.time() >= ack_deadline:
                        break
                    continue

                mtype = msg.get_type()

                if mtype == "MISSION_ACK":
                    mav_result = getattr(msg, "type", -1)
                    if not request_seen and not ignored_clear_ack:
                        self._append_status_log(
                            f"[DEBUG] Pre-request MISSION_ACK result={mav_result} ignored once"
                        )
                        ignored_clear_ack = True
                        try:
                            count_send(ts, tc, total)
                        except TypeError:
                            count_send(ts, tc, total, mission_type)
                        last_resend = time.time()
                        continue
                    if mav_result != 0:
                        raise RuntimeError(
                            f"FC rejected mission during upload: MAV_MISSION_RESULT={mav_result}"
                        )
                    if remaining:
                        raise RuntimeError(
                            f"FC ACKed mission before requesting all items: {sorted(remaining)}"
                        )
                    upload_ok = True
                    break

                # MISSION_REQUEST or MISSION_REQUEST_INT
                seq = msg.seq
                if 0 <= seq < total:
                    request_seen = True
                    _send_item(seq, full_items[seq])
                    remaining.discard(seq)
                    if not remaining and ack_deadline is None:
                        ack_deadline = time.time() + 5
        finally:
            # Always release the queue so the receiver loop resumes normally
            self.processor.upload_queue = None

        if not upload_ok:
            if remaining:
                raise RuntimeError(
                    f"Mission upload timed out; unseqd items: {sorted(remaining)}"
                )
            raise RuntimeError("Mission upload completed, but FC never sent final ACK")

        # ── 3. Set current item to 1 (TAKEOFF after HOME) ─────────────────
        # After upload, move off HOME and point at TAKEOFF.
        try:
            mav.mission_set_current_send(ts, tc, 1)
            self._append_status_log("[DEBUG] mission_set_current seq=1")
        except Exception as e_cur:
            self._append_status_log(f"[WARN] mission_set_current: {e_cur}")

    def _publish_mission_ack(self, payload):
        if not self._connected:
            return
        self.client.publish(MISSION_ACK_TOPIC, json.dumps(payload))

    def _mission_ack_payload(self, *, mission_id, task_id, result, detail):
        return {
            "mission_id": mission_id,
            "task_id": task_id,
            "drone_id": self.drone_id,
            "result": result,
            "detail": detail,
            "timestamp": time.time(),
        }

    def _ack_payload(self, *, cmd_id, command, result, detail):
        return {
            "cmd_id": cmd_id,
            "drone_id": self.drone_id,
            "command": command,
            "result": result,
            "detail": detail,
            "timestamp": time.time(),
        }

    def _append_status_log(self, entry):
        with self.lock:
            _record_status_entry(self.state, entry, drone_id=self.drone_id)

    def _telemetry_payload(self):
        """Build the payload that matches the swarmsim schema."""
        with self.lock:
            s = dict(self.state)

        # Derive mission_role and status (hardware drone defaults)
        prearm_ok = s["prearm_ok"]
        armed     = s["armed"]
        status    = "ACTIVE" if armed else ("READY" if prearm_ok else "GROUNDED")

        return {
            # ── Identity ─────────────────────────────────────
            "drone_id":    self.drone_id,
            "source":      "EDGE_AGENT",
            "mission_role": "",
            # ── Position ─────────────────────────────────────
            "latitude":    s["latitude"],
            "longitude":   s["longitude"],
            "altitude_m":  s["altitude_m"],
            "relative_alt_m": s["relative_alt_m"],
            # ── Motion ───────────────────────────────────────
            "velocity_mps":  s["velocity_mps"],
            "speed_mps":     s["speed_mps"],
            "velocity":      s["velocity_mps"],
            "heading_deg":   s["heading_deg"],
            # ── Battery ──────────────────────────────────────
            "battery_pct":  s["battery_pct"],
            "battery":      s["battery_pct"],
            "voltage_v":    s["voltage_v"],
            # ── GPS ──────────────────────────────────────────
            "gps_fix":             s["gps_fix"],
            "satellites_visible":  s["satellites_visible"],
            # ── State ────────────────────────────────────────
            "status":   status,
            "mode":     s["mode"],
            "armed":    armed,
            # ── Attitude (extra) ─────────────────────────────
            "roll_deg":  s["roll_deg"],
            "pitch_deg": s["pitch_deg"],
            "yaw_deg":   s["yaw_deg"],
            # ── Health ───────────────────────────────────────
            "ekf_ok":     s["ekf_ok"],
            "vibe_x":     s["vibe_x"],
            "vibe_y":     s["vibe_y"],
            "vibe_z":     s["vibe_z"],
            # ── Meta ─────────────────────────────────────────
            "timestamp":   time.time(),
            "msg_count":   s["msg_count"],
        }

    def _status_payload(self):
        with self.lock:
            s = dict(self.state)
        return {
            "drone_id":         self.drone_id,
            "source":           "EDGE_AGENT",
            "prearm_ok":        s["prearm_ok"],
            "prearm_failures":  s["prearm_failures"],
            "ekf_ok":           s["ekf_ok"],
            "ekf_flags":        s["ekf_flags"],
            "armed":            s["armed"],
            "mode":             s["mode"],
            "status_log":       s["status_log"][:5],
            "timestamp":        time.time(),
        }

    def run_forever(self):
        """Publish loop at self.hz. Blocks."""
        interval = 1.0 / self.hz
        tele_topic   = f"fleet/{self.drone_id}/telemetry"
        status_topic = f"fleet/{self.drone_id}/status"
        cycle = 0

        while True:
            t0 = time.time()
            if self._connected:
                # Always publish telemetry
                payload = self._telemetry_payload()
                self.client.publish(tele_topic, json.dumps(payload))

                # Publish status every 5 cycles
                if cycle % 5 == 0:
                    sp = self._status_payload()
                    self.client.publish(status_topic, json.dumps(sp))

                cycle += 1

            elapsed = time.time() - t0
            time.sleep(max(0, interval - elapsed))


# ─── Console display ──────────────────────────────────────────────────────────

def print_status(state, lock, drone_id, broker, hz, start_time):
    import os
    os.system("cls" if os.name == "nt" else "clear")

    with lock:
        s = dict(state)

    now     = datetime.now().strftime("%H:%M:%S")
    uptime  = f"{time.time() - start_time:.0f}s"
    armed   = "🔴 ARMED" if s["armed"] else "🟢 DISARMED"
    lat     = f"{s['latitude']:.6f}"  if s["latitude"]  is not None else "?"
    lon     = f"{s['longitude']:.6f}" if s["longitude"] is not None else "?"
    alt     = f"{s['altitude_m']:.1f}m" if s["altitude_m"] is not None else "?"
    rel_alt = f"{s['relative_alt_m']:.1f}m" if s["relative_alt_m"] is not None else "?"
    v       = f"{s['voltage_v']:.2f}V"  if s["voltage_v"]  is not None else "?"
    pct     = f"{s['battery_pct']}%"
    spd     = f"{s['velocity_mps']:.2f}m/s"
    ekf     = "OK" if s["ekf_ok"] else ("FAIL" if s["ekf_ok"] is not None else "?")
    prearm  = "✅ CLEAR" if s["prearm_ok"] else "❌ FAIL"

    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  AIP POC-2 · Drone Gateway  [{now}]  Uptime: {uptime:<6}       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  DroneID: {drone_id}   Broker: {broker}   Rate: {hz}Hz   Msgs: {s['msg_count']}")
    print(f"  Mode: {s['mode']:<18}  {armed}")
    print()
    print(f"  MQTT publishing to:  fleet/{drone_id}/telemetry")
    print(f"                       fleet/{drone_id}/status")
    print(f"  MQTT commands:       fleet/{drone_id}/command")
    print(f"  MQTT missions:       fleet/{drone_id}/mission")
    print()
    print("  ── Telemetry ────────────────────────────────────────────────")
    print(f"  Position    lat={lat}  lon={lon}  alt={alt}  rel={rel_alt}")
    print(f"  Battery     {v}  {pct}  current={s['current_a']}A")
    print(f"  GPS         fix={s['gps_fix']}  sats={s['satellites_visible']}")
    print(f"  EKF         {ekf}   Vibe x={s['vibe_x']} y={s['vibe_y']} z={s['vibe_z']}")
    print(f"  Attitude    roll={s['roll_deg']}°  pitch={s['pitch_deg']}°  yaw={s['yaw_deg']}°")
    print(f"  Speed       {spd}")
    print()
    print(f"  PreArm: {prearm}")
    for f in s["prearm_failures"][:4]:
        print(f"    ⚠  {f}")
    print()
    print("  ── Status Log ───────────────────────────────────────────────")
    for entry in s["status_log"][:5]:
        print(f"  {entry}")
    if not s["status_log"]:
        print("  (no messages yet)")
    print()
    print("  Press Ctrl+C to stop gateway")


# ─── DroneSession: wraps one port + one droneId ──────────────────────────────

class DroneSession:
    """Lifecycle for a single MAVLink port → MQTT publishing pair."""

    def __init__(self, port, baud, drone_id, broker, mqtt_port, hz):
        self.drone_id   = drone_id
        self.port       = port
        self.baud       = baud
        self.state      = _empty_state()
        self.state["enable_run_log"] = True
        self.lock       = threading.Lock()
        self.start_time = None
        self.connected  = False
        self.proc = MavlinkProcessor(port, baud, self.state, self.lock, drone_id=drone_id)
        self.pub  = MqttPublisher(broker, mqtt_port, drone_id, hz, self.state, self.lock, self.proc)

    def connect(self) -> bool:
        if not self.proc.connect():
            return False
        if not self.pub.connect():
            return False
        self.connected  = True
        self.start_time = time.time()
        return True

    def start_threads(self):
        threading.Thread(
            target=self.proc.run_forever, daemon=True,
            name=f"mav-rx-{self.drone_id}").start()
        threading.Thread(
            target=self.pub.run_forever, daemon=True,
            name=f"mqtt-pub-{self.drone_id}").start()


# ─── Multi-drone console ──────────────────────────────────────────────────────

def print_multi_status(sessions: list, broker: str, hz: float):
    import os
    os.system("cls" if os.name == "nt" else "clear")
    now = datetime.now().strftime("%H:%M:%S")

    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  AIP POC-2 · Multi-Drone Gateway  [{now}]                  ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Broker: {broker}   Rate: {hz}Hz   Drones: {len(sessions)}")
    print()

    for s in sessions:
        uptime = f"{time.time() - s.start_time:.0f}s" if s.start_time else "?"
        with s.lock:
            st   = dict(s.state)
        armed = "🔴 ARMED" if st["armed"] else "🟢 DISARMED"
        lat   = f"{st['latitude']:.6f}"  if st["latitude"]  else "?"
        lon   = f"{st['longitude']:.6f}" if st["longitude"] else "?"
        alt   = f"{st['altitude_m']:.1f}m" if st["altitude_m"] else "?"
        v     = f"{st['voltage_v']:.2f}V" if st["voltage_v"] else "?"
        pct   = f"{st['battery_pct']}%"
        prearm = "✅" if st["prearm_ok"] else "❌"

        print(f"  ┌─ {s.drone_id}  [{s.port} @{s.baud}]  Uptime: {uptime}  Msgs: {st['msg_count']}")
        print(f"  │  {armed}   Mode: {st['mode']}   PreArm: {prearm}")
        print(f"  │  Pos:  lat={lat}  lon={lon}  alt={alt}")
        print(f"  │  Bat:  {v}  {pct}   GPS: fix={st['gps_fix']} sats={st['satellites_visible']}")
        print(f"  │  EKF:  {'OK' if st['ekf_ok'] else 'FAIL'}   "
              f"Vibe: x={st['vibe_x']} y={st['vibe_y']} z={st['vibe_z']}")
        print(f"  └─ MQTT: fleet/{s.drone_id}/telemetry")
        print()

    print("  Press Ctrl+C to stop all gateways")


# ─── Parse --ports argument ───────────────────────────────────────────────────

def parse_ports_arg(ports_str: str) -> list:
    """
    Parse --ports COM6:HW-001,COM3:HW-002 into list of (port, drone_id) tuples.
    Also supports just port names:  COM6,COM3  → (COM6, HW-001), (COM3, HW-002)
    """
    entries = [e.strip() for e in ports_str.split(",") if e.strip()]
    result  = []
    for i, entry in enumerate(entries):
        if ":" in entry:
            port, drone_id = entry.split(":", 1)
        else:
            port     = entry
            drone_id = f"HW-{i+1:03d}"
        result.append((port.strip(), drone_id.strip()))
    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="POC-2: MAVLink → MQTT drone gateway (single or multi-port)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single drone (auto-detect):
    python drone_gateway.py

  Single drone (explicit):
    python drone_gateway.py --port COM6 --baud 57600

  Multi-drone (O5):
    python drone_gateway.py --ports COM6:HW-001,COM3:HW-002
    python drone_gateway.py --ports COM6,COM3,COM7
        """
    )
    # Single-port args (backward compatible)
    parser.add_argument("--port",      default=None,             help="COM port, single drone (auto-detect if omitted)")
    parser.add_argument("--baud",      type=int, default=57600,  help="Baud rate (default 57600)")
    parser.add_argument("--drone-id",  default=DEFAULT_DRONE_ID, help=f"MQTT drone ID, single mode (default {DEFAULT_DRONE_ID})")
    # Multi-port args (O5)
    parser.add_argument("--ports",     default=None,
                        help="Multi-drone: COM6:HW-001,COM3:HW-002  (overrides --port/--drone-id)")
    # Shared args
    parser.add_argument("--broker",    default=DEFAULT_BROKER,    help=f"MQTT broker host (default {DEFAULT_BROKER})")
    parser.add_argument("--mqtt-port", type=int, default=DEFAULT_PORT_NUM, help=f"MQTT broker port (default {DEFAULT_PORT_NUM})")
    parser.add_argument("--hz",        type=float, default=DEFAULT_HZ,    help=f"Publish rate in Hz (default {DEFAULT_HZ})")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  AIP POC-2 · Drone Gateway  (MAVLink → MQTT bridge)         ║")
    print("║  ARM / DISARM / FORCE_ARM  ·  telemetry via MQTT           ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  ⚠️  Make sure Mission Planner is CLOSED (port conflict).")
    print(f"  Run log file: {RUN_LOG_PATH}")
    print()

    # ── Build port list ────────────────────────────────────────────────────────
    if args.ports:
        port_list = parse_ports_arg(args.ports)
    else:
        port_list = [(args.port, args.drone_id)]   # None port = auto-detect

    sessions = []

    for idx, (port, drone_id) in enumerate(port_list, 1):
        label = port or "auto-detect"
        print(f"  [{idx}/{len(port_list)}] Connecting {drone_id}  port={label}  baud={args.baud}...")
        session = DroneSession(port, args.baud, drone_id, args.broker, args.mqtt_port, args.hz)
        if not session.connect():
            print(f"  ❌  {drone_id} ({label}) — no heartbeat received.")
            print("      • Drone powered ON?")
            print("      • Mission Planner closed?")
            print(f"      • Try:  --port COM6  or  --port COM3  --baud {args.baud}")
            if len(port_list) == 1:
                sys.exit(1)
            else:
                print(f"      ⚠️  Skipping {drone_id}, continuing with remaining ports...")
                continue
        print(f"      ✅  {drone_id} connected  →  fleet/{drone_id}/telemetry")
        sessions.append(session)

    if not sessions:
        print("\n❌  No drones connected. Exiting.")
        sys.exit(1)

    print()
    print(f"  🟢  Gateway running  —  {len(sessions)} drone(s) active")
    print()

    for s in sessions:
        s.start_threads()

    start_time = time.time()
    multi       = len(sessions) > 1

    try:
        while True:
            if multi:
                print_multi_status(sessions, args.broker, args.hz)
            else:
                print_status(sessions[0].state, sessions[0].lock,
                             sessions[0].drone_id, args.broker, args.hz, start_time)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n\n  Gateway stopped. Goodbye.")


if __name__ == "__main__":
    main()
