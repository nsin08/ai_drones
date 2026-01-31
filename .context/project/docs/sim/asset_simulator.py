#!/usr/bin/env python3
import argparse
import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict

import paho.mqtt.client as mqtt

def now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat()

def offset_latlon(lat: float, lon: float, north_m: float, east_m: float) -> (float, float):
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--asset-id", default="ASSET-TRUCK-07")
    ap.add_argument("--topic", default="", help="Override topic. Default: assets/<assetId>/pos")
    ap.add_argument("--lat", type=float, default=28.6141)
    ap.add_argument("--lon", type=float, default=77.2094)
    ap.add_argument("--speed-mps", type=float, default=8.0)
    ap.add_argument("--heading-deg", type=float, default=90.0)
    ap.add_argument("--hz", type=float, default=1.0)
    ap.add_argument("--radius-m", type=float, default=200.0, help="If >0, move in a circle of this radius")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    topic = args.topic.strip() or f"assets/{args.asset_id}/pos"
    period = 1.0 / args.hz

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"asset-sim-{args.asset_id}")
    client.connect(args.broker, args.port, 60)
    client.loop_start()

    # Motion model:
    # - If radius_m > 0 => circular motion around starting point
    # - else => straight line along heading
    base_lat, base_lon = args.lat, args.lon
    t0 = time.time()

    print(f"[asset_simulator] publishing {args.asset_id} to {topic} @ {args.hz} Hz")
    try:
        while True:
            t = time.time() - t0

            if args.radius_m > 0:
                # angular speed w = v/r
                w = args.speed_mps / max(1.0, args.radius_m)  # rad/sec
                ang = w * t
                north = math.cos(ang) * args.radius_m
                east = math.sin(ang) * args.radius_m
                lat, lon = offset_latlon(base_lat, base_lon, north, east)
                heading = (math.degrees(ang) + 90.0) % 360.0
            else:
                # straight line
                heading = args.heading_deg % 360.0
                rad = math.radians(heading)
                north = math.cos(rad) * args.speed_mps * t
                east = math.sin(rad) * args.speed_mps * t
                lat, lon = offset_latlon(base_lat, base_lon, north, east)

            msg: Dict[str, Any] = {
                "assetId": args.asset_id,
                "ts": now_rfc3339(),
                "lat": float(lat),
                "lon": float(lon),
                "heading_deg": float(heading),
                "speed_mps": float(args.speed_mps)
            }

            client.publish(topic, json.dumps(msg), qos=1, retain=False)
            time.sleep(period)

    except KeyboardInterrupt:
        print("\n[asset_simulator] stopping...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
