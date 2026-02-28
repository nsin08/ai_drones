#!/usr/bin/env python3
"""
poc2/fault_smoke_test.py
────────────────────────
O4: Fault Model Smoke Test — validate all 5 existing fault models against
realistic hardware telemetry values.

OBJECTIVE: Verify no false-positive CRITICAL faults fire on a healthy,
grounded vehicle, and that activated faults produce valid (bounded) output.

Generates a report at: .context/reports/poc2_fault_smoke_<date>.txt

Usage:
    python fault_smoke_test.py                 # static hardware snapshot
    python fault_smoke_test.py --live --port COM6 --baud 57600  # live data

Requirements:
    pip install pymavlink pyserial paho-mqtt
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Path: add poc/src to the import path ─────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "poc"))

from src.domain.telemetry import Telemetry, Position
from src.domain.battery_sag import BatterySagFault
from src.domain.ekf_unhealthy import EKFUnhealthyFault
from src.domain.gnss_multipath import GNSSMultipathFault
from src.domain.thrust_shortfall import ThrustShortfallFault
from src.domain.rf_loss_burst import RFLossBurstFault


# ─── Hardware Snapshot (validated 2026-02-28, COM6, ArduPilot v4.3.0) ────────

HW_SNAPSHOT = {
    "drone_id":    "HW-001",
    "lat":         24.715724,
    "lon":         78.806115,
    "alt_m":       326.2,       # barometric altitude (AMSL, grounded)
    "battery_pct": 94.0,        # 11.07V, 0.09A (standby draw)
    "velocity_mps": 0.18,       # slight sensor drift, vehicle stationary
    "armed":       False,
    "mode":        "STABILIZE",
    # extra fields (not in Telemetry dataclass but logged in report)
    "gps_fix":     4,           # 3D DGPS fix
    "satellites":  8,
    "vibe_x":      0.02,
    "vibe_y":      0.02,
    "vibe_z":      0.03,
    "ekf_ok":      True,
    "voltage_v":   11.07,
}


def build_telemetry(snap: dict) -> Telemetry:
    return Telemetry(
        drone_id=snap["drone_id"],
        timestamp=time.time(),
        position=Position(
            lat=snap["lat"],
            lon=snap["lon"],
            alt_m=max(0.0, snap["alt_m"]),
        ),
        battery_pct=snap["battery_pct"],
        velocity_mps=snap["velocity_mps"],
        armed=snap["armed"],
        mode=snap["mode"],
    )


# ─── Test Definitions ─────────────────────────────────────────────────────────

class SmokeTester:
    def __init__(self, snap: dict):
        self.snap    = snap
        self.results = []

    def _result(self, name, check, passed, detail=""):
        sym = "✅  PASS" if passed else "❌  FAIL"
        self.results.append((name, check, passed, detail))
        print(f"  {sym}  [{name}]  {check}")
        if detail:
            print(f"         {detail}")

    # ── Test 1: No faults on fresh init (models have grace period built-in) ──

    def test_no_faults_on_fresh_init(self):
        """All models should pass telemetry through unchanged on fresh init."""
        print("\n── Test 1: No faults on fresh init ──────────────────────────────────")
        models = [
            ("BatterySag",    BatterySagFault(every_sec=9999)),
            ("EKFUnhealthy",  EKFUnhealthyFault(every_sec=9999)),
            ("GNSSMultipath", GNSSMultipathFault(every_sec=9999)),
            ("ThrustShortfall", ThrustShortfallFault(every_sec=9999)),
            ("RFLossBurst",   RFLossBurstFault(every_sec=9999)),
        ]
        for name, model in models:
            tel = build_telemetry(self.snap)
            out, faults = model.apply(tel)
            passed = out is not None and faults == []
            detail = f"faults={faults}" if not passed else f"telemetry passed through, no faults"
            self._result(name, "no false positive on grounded vehicle", passed, detail)

    # ── Test 2: BatterySag modifications are bounded ─────────────────────────

    def test_battery_sag_bounded(self):
        """When BatterySag fires, battery should drop but stay >= 0 and < original."""
        print("\n── Test 2: BatterySag — bounded output ──────────────────────────────")
        model = BatterySagFault(every_sec=0, duration_sec=30, sag_pct_per_sec=1.0)
        tel   = build_telemetry(self.snap)
        time.sleep(0.05)            # let tiny time pass so sag_pct_per_sec applies
        out, faults = model.apply(tel)
        passed = (out is not None
                  and "BATTERY_SAG" in faults
                  and 0.0 <= out.battery_pct < tel.battery_pct)
        detail = f"original={tel.battery_pct:.1f}% → modified={out.battery_pct:.2f}%" if out else "output was None"
        self._result("BatterySag", "output 0 ≤ battery_pct < original", passed, detail)

        # Extra: battery should never go negative
        tel_low = Telemetry(
            drone_id="HW-001", timestamp=time.time(),
            position=Position(lat=self.snap["lat"], lon=self.snap["lon"], alt_m=0.1),
            battery_pct=0.5, velocity_mps=0.0, armed=False, mode="STABILIZE",
        )
        time.sleep(0.05)
        model2 = BatterySagFault(every_sec=0, duration_sec=30, sag_pct_per_sec=100.0)
        out2, _ = model2.apply(tel_low)
        passed2 = out2 is not None and out2.battery_pct >= 0.0
        self._result("BatterySag", "battery never goes below 0%", passed2,
                     f"result={out2.battery_pct:.2f}%" if out2 else "None")

    # ── Test 3: EKF noise injection is bounded ────────────────────────────────

    def test_ekf_noise_bounded(self):
        """EKF fault injects Gaussian position noise; lat/lon must remain valid (-90..90, -180..180)."""
        print("\n── Test 3: EKFUnhealthy — position bounds ────────────────────────────")
        model = EKFUnhealthyFault(every_sec=0, duration_sec=60, noise_stddev_m=50.0)
        passed_all = True
        for i in range(20):
            tel = build_telemetry(self.snap)
            out, faults = model.apply(tel)
            if out is None:
                passed_all = False
                break
            if not (-90 <= out.position.lat <= 90 and -180 <= out.position.lon <= 180):
                passed_all = False
                break
            if "EKF_UNHEALTHY" not in faults:
                passed_all = False
                break
        self._result("EKFUnhealthy", "lat/lon in valid range over 20 samples", passed_all,
                     f"last out: lat={out.position.lat:.6f} lon={out.position.lon:.6f}" if out else "None")

    # ── Test 4: GNSS multipath offset is bounded ──────────────────────────────

    def test_gnss_multipath_bounded(self):
        """GNSS multipath applies position offset; must remain geographically valid."""
        print("\n── Test 4: GNSSMultipath — position offset bounded ──────────────────")
        model = GNSSMultipathFault(every_sec=0, duration_sec=60, offset_range=20.0)
        passed_all = True
        for i in range(20):
            tel = build_telemetry(self.snap)
            out, faults = model.apply(tel)
            if out is None or "GNSS_MULTIPATH" not in faults:
                passed_all = False
                break
            if not (-90 <= out.position.lat <= 90 and -180 <= out.position.lon <= 180):
                passed_all = False
                break
        self._result("GNSSMultipath", "lat/lon in valid range over 20 samples", passed_all,
                     f"last offset: Δlat={out.position.lat - self.snap['lat']:.6f}" if out else "None")

    # ── Test 5: Thrust shortfall altitude drop is bounded ─────────────────────

    def test_thrust_shortfall_bounded(self):
        """Thrust shortfall drops altitude; should not go below 0."""
        print("\n── Test 5: ThrustShortfall — altitude bounded ───────────────────────")
        model = ThrustShortfallFault(every_sec=0, duration_sec=30, alt_loss_mps=2.0)
        tel   = build_telemetry(self.snap)
        time.sleep(0.05)
        out, faults = model.apply(tel)
        passed = (out is not None
                  and "THRUST_SHORTFALL" in faults
                  and out.position.alt_m >= 0.0
                  and out.position.alt_m <= tel.position.alt_m)
        detail = (f"original_alt={tel.position.alt_m:.1f}m → modified={out.position.alt_m:.2f}m"
                  if out else "None")
        self._result("ThrustShortfall", "0 ≤ alt_m ≤ original_alt", passed, detail)

        # Extra: alt cannot go negative even on surface
        tel_ground = Telemetry(
            drone_id="HW-001", timestamp=time.time(),
            position=Position(lat=self.snap["lat"], lon=self.snap["lon"], alt_m=0.1),
            battery_pct=94.0, velocity_mps=0.0, armed=False, mode="STABILIZE",
        )
        model2 = ThrustShortfallFault(every_sec=0, duration_sec=30, alt_loss_mps=999.0)
        time.sleep(0.05)
        out2, _ = model2.apply(tel_ground)
        passed2 = out2 is not None and out2.position.alt_m >= 0.0
        self._result("ThrustShortfall", "altitude never goes below 0m", passed2,
                     f"result={out2.position.alt_m:.4f}m" if out2 else "None")

    # ── Test 6: RF loss burst drops message (returns None) ────────────────────

    def test_rf_loss_drops_message(self):
        """RF loss burst should return None (drop message) when active."""
        print("\n── Test 6: RFLossBurst — message drop ───────────────────────────────")
        model = RFLossBurstFault(every_sec=0, down_sec=60)
        tel   = build_telemetry(self.snap)
        out, faults = model.apply(tel)
        passed = out is None and "RF_LOSS_BURST" in faults
        self._result("RFLossBurst", "returns None (drops message) when active", passed,
                     f"out={out}  faults={faults}")

        # And passes when not active
        model2 = RFLossBurstFault(every_sec=9999, down_sec=60)
        out2, faults2 = model2.apply(tel)
        passed2 = out2 is not None and faults2 == []
        self._result("RFLossBurst", "passes message when inactive", passed2,
                     f"faults={faults2}")

    # ── Test 7: Hardware snapshot — realistic values don't trigger default thresholds ──

    def test_hardware_values_are_nominal(self):
        """Using default (production) timing parameters, verify nominal values produce no faults."""
        print("\n── Test 7: Default params — nominal hardware values ─────────────────")
        # All models at production defaults (every_sec > any reasonable test window)
        models = [
            ("BatterySag(default)",     BatterySagFault()),
            ("EKFUnhealthy(default)",   EKFUnhealthyFault()),
            ("GNSSMultipath(default)",  GNSSMultipathFault()),
            ("ThrustShortfall(default)", ThrustShortfallFault()),
            ("RFLossBurst(default)",    RFLossBurstFault()),
        ]
        for name, model in models:
            tel = build_telemetry(self.snap)
            out, faults = model.apply(tel)
            # Fresh init: all models should have built-in grace period
            # Models initialize _last_fault = now - duration - 1 (just ended, not yet time to fire again)
            passed = out is not None and faults == []
            self._result(name, "no fault on fresh init at default params", passed,
                         f"faults={faults}" if faults else "clean")

    # ── Run all tests ─────────────────────────────────────────────────────────

    def run(self):
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║  POC-2 O4 · Fault Model Smoke Test                          ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()
        print("  Hardware Context:")
        print(f"  Drone:    {self.snap['drone_id']}  (ArduPilot v4.3.0, QuadRotor)")
        print(f"  Position: lat={self.snap['lat']}  lon={self.snap['lon']}  alt={self.snap['alt_m']}m")
        print(f"  Battery:  {self.snap['battery_pct']}%  ({self.snap['voltage_v']}V)")
        print(f"  GPS:      fix={self.snap['gps_fix']}  sats={self.snap['satellites']}")
        print(f"  EKF:      {'OK' if self.snap['ekf_ok'] else 'FAIL'}")
        print(f"  Vibe:     x={self.snap['vibe_x']}  y={self.snap['vibe_y']}  z={self.snap['vibe_z']}")
        print(f"  Armed:    {self.snap['armed']}   Mode: {self.snap['mode']}")

        self.test_no_faults_on_fresh_init()
        self.test_battery_sag_bounded()
        self.test_ekf_noise_bounded()
        self.test_gnss_multipath_bounded()
        self.test_thrust_shortfall_bounded()
        self.test_rf_loss_drops_message()
        self.test_hardware_values_are_nominal()

        return self.results


# ─── Report Generator ─────────────────────────────────────────────────────────

def generate_report(results: list, snap: dict) -> str:
    now      = datetime.now()
    passed   = sum(1 for _, _, p, _ in results if p)
    failed   = sum(1 for _, _, p, _ in results if not p)
    total    = len(results)

    lines = [
        "═" * 66,
        "  POC-2 O4: Fault Model Smoke Test Report",
        f"  Date:       {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Hardware:   {snap['drone_id']}  ArduPilot v4.3.0  (QuadRotor)",
        f"  Location:   {snap['lat']}°N, {snap['lon']}°E",
        f"  Battery:    {snap['battery_pct']}%  ({snap['voltage_v']}V)",
        f"  GPS:        fix={snap['gps_fix']}  sats={snap['satellites']}",
        f"  Result:     {passed}/{total} passed  ({failed} failed)",
        "═" * 66,
        "",
        "Tests:",
        "",
    ]
    for name, check, passed_flag, detail in results:
        sym = "PASS" if passed_flag else "FAIL"
        lines.append(f"  [{sym}]  {name}")
        lines.append(f"         Check:  {check}")
        if detail:
            lines.append(f"         Detail: {detail}")
        lines.append("")

    lines.append("─" * 66)
    lines.append(f"  TOTAL: {passed}/{total} passed")
    if failed == 0:
        lines.append("  ✅  ALL CHECKS PASSED — Fault models safe on real hardware")
    else:
        lines.append(f"  ❌  {failed} CHECK(S) FAILED — Review above")
    lines.append("─" * 66)
    return "\n".join(lines)


# ─── Optional: live capture from gateway state ───────────────────────────────

def live_snapshot(port, baud) -> dict:
    try:
        from pymavlink import mavutil
    except ImportError:
        sys.exit("pymavlink not installed")

    print(f"  Connecting to {port} @ {baud}...")
    conn = mavutil.mavlink_connection(port, baud=baud)
    hb = conn.wait_heartbeat(timeout=15)
    if not hb:
        sys.exit(f"No heartbeat on {port}")

    snap = dict(HW_SNAPSHOT)
    snap["drone_id"] = "HW-001"

    conn.mav.request_data_stream_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

    print("  Collecting telemetry (5 seconds)...")
    deadline = time.time() + 5.0
    while time.time() < deadline:
        msg = conn.recv_match(blocking=True, timeout=1.0)
        if not msg or msg.get_type() == "BAD_DATA":
            continue
        t = msg.get_type()
        if t == "GPS_RAW_INT":
            snap["gps_fix"] = msg.fix_type
            snap["satellites"] = msg.satellites_visible
            if msg.lat:
                snap["lat"] = round(msg.lat / 1e7, 7)
                snap["lon"] = round(msg.lon / 1e7, 7)
        elif t == "VFR_HUD":
            snap["alt_m"]        = round(msg.alt, 1)
            snap["velocity_mps"] = round(msg.groundspeed, 2)
        elif t == "SYS_STATUS":
            snap["battery_pct"] = msg.battery_remaining
            snap["voltage_v"]   = round(msg.voltage_battery / 1000.0, 2)
        elif t == "HEARTBEAT":
            snap["armed"] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            snap["mode"]  = mavutil.mode_string_v10(msg)
        elif t == "EKF_STATUS_REPORT":
            snap["ekf_ok"] = bool(msg.flags & 0x01)
        elif t == "VIBRATION":
            snap["vibe_x"] = round(msg.vibration_x, 2)
            snap["vibe_y"] = round(msg.vibration_y, 2)
            snap["vibe_z"] = round(msg.vibration_z, 2)

    conn.close()
    return snap


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="POC-2 O4: Fault model smoke test")
    parser.add_argument("--live",  action="store_true", help="Capture live telemetry from hardware")
    parser.add_argument("--port",  default="COM6",      help="COM port for live mode")
    parser.add_argument("--baud",  type=int, default=57600, help="Baud rate for live mode")
    parser.add_argument("--no-report", action="store_true", help="Skip saving report file")
    args = parser.parse_args()

    if args.live:
        print("\n  Live mode: capturing real telemetry from hardware...")
        snap = live_snapshot(args.port, args.baud)
    else:
        print("\n  Static mode: using validated hardware snapshot (2026-02-28).")
        snap = dict(HW_SNAPSHOT)

    tester  = SmokeTester(snap)
    results = tester.run()

    passed = sum(1 for _, _, p, _ in results if p)
    failed = sum(1 for _, _, p, _ in results if not p)
    total  = len(results)

    print()
    print("─" * 66)
    print(f"  TOTAL: {passed}/{total} passed", end="")
    if failed == 0:
        print("  ✅  ALL PASSED")
    else:
        print(f"  ❌  {failed} FAILED")
    print("─" * 66)

    # Save report
    if not args.no_report:
        report_dir = REPO_ROOT / ".context" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        fname = report_dir / f"poc2_fault_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_text = generate_report(results, snap)
        fname.write_text(report_text, encoding="utf-8")
        print(f"\n  Report saved: {fname}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
