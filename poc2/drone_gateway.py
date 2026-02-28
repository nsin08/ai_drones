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

READ-ONLY — no arming or flight commands are issued.

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
AUTO_PORTS         = ["COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
                      "COM9", "COM10", "COM11", "COM12"]
AUTO_BAUDS         = [57600, 115200]
SEV_NAMES          = {0: "EMERGENCY", 1: "ALERT", 2: "CRITICAL",
                      3: "ERROR", 4: "WARNING", 5: "NOTICE",
                      6: "INFO", 7: "DEBUG"}


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
    }


def _rad2deg(r):
    import math
    return r * 180.0 / math.pi


# ─── MAVLink message processor ────────────────────────────────────────────────

class MavlinkProcessor:
    """Owns the MAVLink connection and updates the shared state dict."""

    def __init__(self, port, baud, state: dict, lock: threading.Lock):
        self.port  = port
        self.baud  = baud
        self.state = state
        self.lock  = lock
        self.conn  = None

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
                s["mode"]    = mavutil.mode_string_v10(msg)
                s["armed"]   = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                vt = msg.type
                s["vehicle_type"] = mavutil.mavlink.enums["MAV_TYPE"].get(
                    vt, type("x", (), {"name": str(vt)})()).name.replace("MAV_TYPE_", "")
                s["last_heartbeat"] = time.time()

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

            elif t == "EKF_STATUS_REPORT":
                s["ekf_flags"] = msg.flags
                s["ekf_ok"]    = bool(msg.flags & 0x01)

            elif t == "VIBRATION":
                s["vibe_x"] = round(msg.vibration_x, 2)
                s["vibe_y"] = round(msg.vibration_y, 2)
                s["vibe_z"] = round(msg.vibration_z, 2)

            elif t == "STATUSTEXT":
                text     = msg.text.strip()
                sev_name = SEV_NAMES.get(msg.severity, str(msg.severity))
                entry    = f"[{sev_name}] {text}"
                log = s["status_log"]
                if entry not in log:
                    log.insert(0, entry)
                    s["status_log"] = log[:10]

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

    def __init__(self, broker, port, drone_id, hz, state, lock):
        self.broker   = broker
        self.port     = port
        self.drone_id = drone_id
        self.hz       = hz
        self.state    = state
        self.lock     = lock
        self.client   = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connected = False

    def _on_connect(self, client, userdata, flags, reason_code, props=None):
        rc = reason_code if isinstance(reason_code, int) else reason_code.value
        if rc == 0:
            self._connected = True
            print(f"  ✅  MQTT connected  broker={self.broker}:{self.port}")
        else:
            print(f"  ❌  MQTT connect failed  rc={rc}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, props=None):
        self._connected = False
        print(f"  ⚠️   MQTT disconnected (rc={reason_code}), reconnecting...")

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
    print()
    print("  ── Telemetry ────────────────────────────────────────────────")
    print(f"  Position    lat={lat}  lon={lon}  alt={alt}")
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
        self.lock       = threading.Lock()
        self.start_time = None
        self.connected  = False
        self.proc = MavlinkProcessor(port, baud, self.state, self.lock)
        self.pub  = MqttPublisher(broker, mqtt_port, drone_id, hz, self.state, self.lock)

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
    print("║  READ-ONLY — no arming or flight commands                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  ⚠️  Make sure Mission Planner is CLOSED (port conflict).")
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
