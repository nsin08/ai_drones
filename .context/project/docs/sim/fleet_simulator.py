#!/usr/bin/env python3
import argparse
import json
import random
import time
from datetime import datetime, timezone
from typing import Dict, Any

import paho.mqtt.client as mqtt

def now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat()

def mk_drone_id(i: int) -> str:
    return f"D{i:03d}"

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--drones", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--hz", type=float, default=1.0)
    args = ap.parse_args()

    random.seed(args.seed)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"fleet-sim-{args.seed}")
    client.connect(args.broker, args.port, 60)
    client.loop_start()

    # Simple initial geometry around a base point (pick any)
    base_lat, base_lon = 28.6139, 77.2090

    # In-memory state
    states: Dict[str, Dict[str, Any]] = {}
    for i in range(1, args.drones + 1):
        did = mk_drone_id(i)
        states[did] = {
            "lat": base_lat + (random.random() - 0.5) * 0.002,
            "lon": base_lon + (random.random() - 0.5) * 0.002,
            "alt": 20.0 + random.random() * 5,
            "vel": 4.0 + random.random() * 2,
            "armed": True if i <= max(1, args.drones // 2) else False,
            "mode": "GUIDED",
            "battery_pct": 100.0 - random.random() * 5,
            "voltage": 16.0,
            "current": 8.0,
            "rssi": -55.0,
        }

    period = 1.0 / args.hz

    print(f"[fleet_simulator] publishing {args.drones} drones to raw/fleet/<droneId>/telemetry @ {args.hz} Hz")
    try:
        while True:
            t0 = time.time()
            for did, s in states.items():
                # Move a bit
                s["lat"] += (random.random() - 0.5) * 0.00001
                s["lon"] += (random.random() - 0.5) * 0.00001
                s["battery_pct"] = clamp(s["battery_pct"] - 0.01 - random.random() * 0.02, 0, 100)

                # Basic link stats (raw; fault injector will make it realistic)
                raw = {
                    "droneId": did,
                    "ts": now_rfc3339(),
                    "pos": {"lat": s["lat"], "lon": s["lon"], "alt_m": s["alt"], "vel_mps": s["vel"]},
                    "mode": s["mode"],
                    "armed": s["armed"],
                    "battery": {"pct": s["battery_pct"], "voltage_v": s["voltage"], "current_a": s["current"], "sag_model": "linear"},
                    "link": {"rssi": s["rssi"], "packet_loss_pct": 0.0, "jitter_ms": 0.0, "last_gap_ms": 0.0},
                    "nav": {"gps_fix": "3D", "hdop": 1.2, "ekf_ok": True, "ekf_variance": 0.3},
                    "faults": []
                }

                client.publish(f"raw/fleet/{did}/telemetry", json.dumps(raw), qos=1, retain=False)

                # Health at lower rate (cheap)
                if int(time.time()) % 5 == 0:
                    health = {"droneId": did, "ts": now_rfc3339(), "ok": True, "notes": "sim"}
                    client.publish(f"raw/fleet/{did}/health", json.dumps(health), qos=1, retain=True)

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))
    except KeyboardInterrupt:
        print("\n[fleet_simulator] stopping...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
