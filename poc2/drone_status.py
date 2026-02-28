#!/usr/bin/env python3
"""
poc2/drone_status.py
────────────────────
Minimal real-hardware demo: connect to a single ArduPilot drone,
stream live telemetry, and display a ready-to-fly checklist.

READ-ONLY  — no arming, no flight commands issued.

Usage:
    python drone_status.py                  # auto-detect port
    python drone_status.py --port COM3      # explicit port
    python drone_status.py --port COM3 --baud 115200

Requirements:
    pip install pymavlink
    Close Mission Planner before running (port conflict).
"""

import argparse
import os
import sys
import time
from collections import deque
from datetime import datetime

try:
    from pymavlink import mavutil
except ImportError:
    sys.exit("❌  pymavlink not installed.  Run:  pip install pymavlink")


# ─── Configuration ────────────────────────────────────────────────────────────

AUTO_DETECT_PORTS = ["COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
                     "COM9", "COM10", "COM11", "COM12"]
BAUD_RATES        = [57600, 115200]
HEARTBEAT_TIMEOUT = 15      # seconds to wait for first heartbeat
REFRESH_HZ        = 4       # terminal refresh rate
STATUS_LOG_LINES  = 6       # last N STATUSTEXT messages to keep

# ─── Telemetry State ──────────────────────────────────────────────────────────

state = {
    # heartbeat
    "sysid": None,
    "compid": None,
    "vehicle_type": "?",
    "firmware": "?",
    "mode": "?",
    "armed": None,
    "base_mode": 0,
    "custom_mode": 0,

    # attitude
    "roll_deg": None,
    "pitch_deg": None,
    "yaw_deg": None,

    # GPS
    "gps_fix": None,
    "gps_sats": None,
    "gps_lat": None,
    "gps_lon": None,
    "gps_hdop": None,

    # battery
    "voltage_v": None,
    "current_a": None,
    "remaining_pct": None,

    # EKF
    "ekf_ok": None,
    "ekf_flags": 0,

    # vibration
    "vibe_x": None,
    "vibe_y": None,
    "vibe_z": None,
    "clip_count": None,

    # altimeter
    "alt_m": None,
    "groundspeed_ms": None,

    # prearm
    "prearm_ok": True,
    "prearm_msgs": deque(maxlen=STATUS_LOG_LINES),

    # stats
    "msg_count": 0,
    "connected_port": "?",
    "connected_baud": 0,
    "connect_time": None,
}


def import_math():
    import math
    return math


def rad2deg(r):
    import math
    return r * 180.0 / math.pi


# ─── Checklist ────────────────────────────────────────────────────────────────

def checklist():
    """Return list of (label, ok, detail) for the pre-flight checklist."""
    s = state
    items = []

    # GPS 3D Fix
    fix = s["gps_fix"]
    fix_ok = fix is not None and fix >= 3
    fix_names = {0: "NO_GPS", 1: "NO_FIX", 2: "2D", 3: "3D", 4: "3D_DGPS", 5: "RTK_FLOAT", 6: "RTK_FIXED"}
    items.append(("GPS 3D Fix",
                  fix_ok,
                  fix_names.get(fix, "?") + (f"  sats={s['gps_sats']}" if s["gps_sats"] else "")))

    # GPS satellites ≥ 6
    sats = s["gps_sats"]
    items.append(("GPS Sats ≥ 6",
                  sats is not None and sats >= 6,
                  f"{sats} satellites" if sats is not None else "waiting..."))

    # Battery voltage
    v = s["voltage_v"]
    bat_ok = v is not None and v >= 10.5
    items.append(("Battery ≥ 10.5V",
                  bat_ok,
                  f"{v:.2f}V  ({s['remaining_pct']}%)" if v else "waiting..."))

    # EKF
    ekf_ok = s["ekf_ok"]
    items.append(("EKF Healthy",
                  ekf_ok is not None and ekf_ok,
                  "OK" if ekf_ok else ("FAIL" if ekf_ok is not None else "waiting...")))

    # Vibration < 30 m/s²
    vx, vy, vz = s["vibe_x"], s["vibe_y"], s["vibe_z"]
    if vx is not None:
        vmax = max(vx, vy, vz)
        vibe_ok = vmax < 30.0
        vibe_detail = f"x={vx:.1f} y={vy:.1f} z={vz:.1f} m/s²"
    else:
        vibe_ok = None
        vibe_detail = "waiting..."
    items.append(("Vibration < 30", vibe_ok, vibe_detail))

    # No PreArm failures
    items.append(("PreArm Clear",
                  s["prearm_ok"],
                  "All checks passed" if s["prearm_ok"] else "See status log below"))

    return items


# ─── Render ───────────────────────────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def fmt_bool(v, yes="✅", no="❌", maybe="⏳"):
    if v is True:
        return yes
    if v is False:
        return no
    return maybe


def render():
    s = state
    now = datetime.now().strftime("%H:%M:%S")
    elapsed = f"{time.time() - s['connect_time']:.0f}s" if s["connect_time"] else "?"

    clear()

    # ── Header
    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  AIP POC-2 · Single Drone Status Monitor  [{now}]         ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Port: {s['connected_port']}  Baud: {s['connected_baud']}  "
          f"SysID: {s['sysid']}  CompID: {s['compid']}  "
          f"Type: {s['vehicle_type']}  Uptime: {elapsed}")
    print(f"  Mode: {s['mode']:<18}  "
          f"Armed: {fmt_bool(s['armed'], '🔴 ARMED', '🟢 DISARMED', '⏳ ?')}  "
          f"Msgs: {s['msg_count']}")
    print()

    # ── Pre-flight Checklist
    print("  ── Pre-Flight Checklist ─────────────────────────────────────")
    all_ok = True
    for label, ok, detail in checklist():
        sym = fmt_bool(ok)
        if ok is not True:
            all_ok = False
        print(f"  {sym}  {label:<22}  {detail}")

    if all_ok:
        print()
        print("  🟩  ALL CHECKS PASSED — READY TO ARM")
    else:
        print()
        print("  🟥  NOT READY — resolve checklist items above")

    print()

    # ── Live Telemetry
    print("  ── Live Telemetry ───────────────────────────────────────────")

    roll  = f"{s['roll_deg']:+7.1f}°" if s["roll_deg"]  is not None else "     ?"
    pitch = f"{s['pitch_deg']:+7.1f}°" if s["pitch_deg"] is not None else "     ?"
    yaw   = f"{s['yaw_deg']:+7.1f}°"  if s["yaw_deg"]   is not None else "     ?"
    alt   = f"{s['alt_m']:.1f} m"     if s["alt_m"]     is not None else "?"
    gspd  = f"{s['groundspeed_ms']:.2f} m/s" if s["groundspeed_ms"] is not None else "?"
    lat   = f"{s['gps_lat']:.6f}"     if s["gps_lat"]   is not None else "?"
    lon   = f"{s['gps_lon']:.6f}"     if s["gps_lon"]   is not None else "?"
    hdop  = f"{s['gps_hdop']/100:.2f}" if s["gps_hdop"] is not None else "?"

    print(f"  Attitude   roll={roll}  pitch={pitch}  yaw={yaw}")
    print(f"  Position   lat={lat}  lon={lon}  alt={alt}  hdop={hdop}")
    print(f"  Motion     groundspeed={gspd}")

    v    = f"{s['voltage_v']:.2f}V"       if s["voltage_v"]       is not None else "?"
    cur  = f"{s['current_a']:.1f}A"       if s["current_a"]       is not None else "?"
    pct  = f"{s['remaining_pct']}%"       if s["remaining_pct"]   is not None else "?"
    vx   = f"{s['vibe_x']:.1f}"           if s["vibe_x"]          is not None else "?"
    vy   = f"{s['vibe_y']:.1f}"           if s["vibe_y"]          is not None else "?"
    vz   = f"{s['vibe_z']:.1f}"           if s["vibe_z"]          is not None else "?"

    print(f"  Battery    {v}  {cur}  {pct}")
    print(f"  Vibration  x={vx}  y={vy}  z={vz} m/s²")
    print()

    # ── Status Log
    print("  ── Vehicle Status Log ───────────────────────────────────────")
    if s["prearm_msgs"]:
        for entry in s["prearm_msgs"]:
            print(f"  {entry}")
    else:
        print("  (no status messages yet)")

    print()
    print("  Press Ctrl+C to quit")


# ─── MAVLink loop ─────────────────────────────────────────────────────────────

SEV = {0: "EMERGENCY", 1: "ALERT", 2: "CRITICAL", 3: "ERROR",
       4: "WARNING", 5: "NOTICE", 6: "INFO", 7: "DEBUG"}


def process_msg(msg):
    s = state
    s["msg_count"] += 1
    t = msg.get_type()

    if t == "HEARTBEAT":
        s["mode"]        = mavutil.mode_string_v10(msg)
        s["armed"]       = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        s["base_mode"]   = msg.base_mode
        s["custom_mode"] = msg.custom_mode
        vt = msg.type
        s["vehicle_type"] = mavutil.mavlink.enums["MAV_TYPE"].get(vt, type("x", (), {"name": str(vt)})()).name.replace("MAV_TYPE_", "")

    elif t == "ATTITUDE":
        s["roll_deg"]  = rad2deg(msg.roll)
        s["pitch_deg"] = rad2deg(msg.pitch)
        s["yaw_deg"]   = rad2deg(msg.yaw)

    elif t == "GPS_RAW_INT":
        s["gps_fix"]  = msg.fix_type
        s["gps_sats"] = msg.satellites_visible
        s["gps_lat"]  = msg.lat / 1e7
        s["gps_lon"]  = msg.lon / 1e7
        s["gps_hdop"] = msg.eph      # cm

    elif t == "SYS_STATUS":
        s["voltage_v"]       = msg.voltage_battery / 1000.0
        s["current_a"]       = msg.current_battery / 100.0
        s["remaining_pct"]   = msg.battery_remaining

    elif t == "EKF_STATUS_REPORT":
        flags = msg.flags
        s["ekf_flags"] = flags
        # bit 0 = attitude ok, bit 1 = vel horiz ok, bit 3 = pos horiz ok, bit 7 = pred horiz ok
        s["ekf_ok"] = bool(flags & 0x01)        # attitude healthy is minimum

    elif t == "VIBRATION":
        s["vibe_x"]    = msg.vibration_x
        s["vibe_y"]    = msg.vibration_y
        s["vibe_z"]    = msg.vibration_z
        s["clip_count"] = msg.clipping_0

    elif t == "VFR_HUD":
        s["alt_m"]          = msg.alt
        s["groundspeed_ms"] = msg.groundspeed

    elif t == "STATUSTEXT":
        text = msg.text.strip()
        sev  = SEV.get(msg.severity, str(msg.severity))
        entry = f"[{sev:9s}] {text}"
        s["prearm_msgs"].appendleft(entry)
        if "PreArm" in text or "prearm" in text.lower():
            s["prearm_ok"] = False
        # Reset prearm_ok if vehicle reports ready
        if "Ready to arm" in text or "PreArm checks passed" in text:
            s["prearm_ok"] = True


def try_connect(port, baud):
    """Return a mavutil connection or None."""
    try:
        print(f"  Trying {port} @ {baud}...")
        conn = mavutil.mavlink_connection(port, baud=baud)
        hb = conn.wait_heartbeat(timeout=5)
        if hb:
            return conn
        conn.close()
    except Exception as e:
        print(f"  {port}@{baud}: {e}")
    return None


def auto_connect():
    print("\n  Auto-detecting drone port...")
    for port in AUTO_DETECT_PORTS:
        for baud in BAUD_RATES:
            conn = try_connect(port, baud)
            if conn:
                return conn, port, baud
    return None, None, None


def explicit_connect(port, baud):
    print(f"\n  Connecting to {port} @ {baud}...")
    conn = try_connect(port, baud)
    if not conn and baud == 57600:
        print("  57600 failed, trying 115200...")
        conn = try_connect(port, 115200)
        baud = 115200 if conn else baud
    return conn, port, baud


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="POC-2: Single drone status monitor")
    parser.add_argument("--port", default=None, help="COM port, e.g. COM3  (auto-detect if omitted)")
    parser.add_argument("--baud", type=int, default=57600, help="Baud rate (default 57600)")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  AIP POC-2 · Drone Status Monitor                           ║")
    print("║  READ-ONLY — no arming or flight commands                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  ⚠️  Make sure Mission Planner is CLOSED (port conflict).")
    print()

    if args.port:
        conn, port, baud = explicit_connect(args.port, args.baud)
    else:
        conn, port, baud = auto_connect()

    if not conn:
        print()
        print("❌  No heartbeat received on any port.")
        print("    • Is the drone powered ON?")
        print("    • Is Mission Planner closed?")
        print("    • Try --port COM3 --baud 57600  (or 115200)")
        sys.exit(1)

    state["sysid"]          = conn.target_system
    state["compid"]         = conn.target_component
    state["connected_port"] = port
    state["connected_baud"] = baud
    state["connect_time"]   = time.time()

    print(f"\n  ✅  Heartbeat received!  sysid={conn.target_system}  compid={conn.target_component}")
    print(f"      Port={port}  Baud={baud}")
    print("\n  Starting live dashboard in 1 second...")
    time.sleep(1)

    # Request all data streams at 4 Hz
    conn.mav.request_data_stream_send(
        conn.target_system,
        conn.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL,
        4,    # 4 Hz
        1,    # start
    )

    interval  = 1.0 / REFRESH_HZ
    last_draw = 0.0

    try:
        while True:
            msg = conn.recv_match(blocking=True, timeout=1.0)
            if msg and msg.get_type() != "BAD_DATA":
                process_msg(msg)

            now = time.time()
            if now - last_draw >= interval:
                render()
                last_draw = now

    except KeyboardInterrupt:
        print("\n\n  Disconnected. Goodbye.")


if __name__ == "__main__":
    main()
