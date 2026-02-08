"""
SwarmSim - Virtual drone fleet simulator for V3 Mission Control

Features:
- Configurable fleet (10-17 drones, SIM-### ID namespace)
- 1 Hz telemetry (0.5 Hz if >15 drones), +/-50 ms jitter
- Formation offsets (LEADER, WINGMAN, SCOUT, POINT_MAN, RELAY, GUARD, CARGO)
- Battery drain: ~0.5%/min, start 85-95%
- Command ACK with 100-300 ms simulated latency
- Formation break rules (leader HOLD/RETURN -> PAUSED)
- FORMATION_COMPROMISED event when >40% OOF for >10 s
- Optional SIM_FAIL_RATE for realistic demo failures
"""

import argparse
import json
import math
import os
import random
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
SIM_FAIL_RATE = float(os.getenv("SIM_FAIL_RATE", "0.02"))  # 2% ACK failure
TELEMETRY_HZ = 1.0
BASE_LAT = 28.6139
BASE_LON = 77.2090
BASE_ALT = 50.0  # metres

FORMATION_OFFSETS = {
    "LEADER":    (0, 0),
    "WINGMAN":   (30, 0),       # lateral offset
    "SCOUT":     (60, 0),       # wider arc
    "POINT_MAN": (0, 45),       # forward
    "RELAY":     (0, -40),      # trailing
    "GUARD":     (-30, 0),      # lateral opposite
    "CARGO":     (0, -20),      # trailing centre
}

DEFAULT_ROLES = [
    "LEADER", "WINGMAN", "WINGMAN", "SCOUT",
    "POINT_MAN", "RELAY", "GUARD", "WINGMAN",
    "WINGMAN", "SCOUT", "GUARD", "CARGO",
    "WINGMAN", "WINGMAN", "RELAY", "SCOUT", "WINGMAN",
]

# ---------------------------------------------------------------------------
# Drone model
# ---------------------------------------------------------------------------
class SimDrone:
    def __init__(self, idx, role, total_drones):
        self.drone_id = f"SIM-{idx:03d}"
        self.role = role
        self.status = "ACTIVE"
        self.mode = "AUTO"
        self.armed = True
        self.battery = random.uniform(85, 95)
        self.altitude = BASE_ALT + random.uniform(-2, 2)
        self.speed = random.uniform(8, 12)  # m/s
        self.heading = 0.0
        self.gps_fix = 3
        self.satellites = random.randint(10, 16)

        # Position offsets (in metres, converted to lat/lon)
        off = FORMATION_OFFSETS.get(role, (0, 0))
        lat_off = off[1] / 111_320               # ~1 deg = 111.32 km
        lon_off = off[0] / (111_320 * math.cos(math.radians(BASE_LAT)))
        self.lat = BASE_LAT + lat_off
        self.lon = BASE_LON + lon_off

        # Patrol waypoint index
        self.wp_idx = 0
        self.waypoints = []
        self.hold = False
        self.disabled = False
        self.returning = False

    def tick(self, dt, waypoints, leader_pos):
        """Advance one simulation step."""
        # Battery drain: ~0.5%/min -> 0.00833%/s
        if self.status != "DISABLED":
            self.battery = max(0, self.battery - 0.00833 * dt)
        if self.battery < 1:
            self.status = "DEAD"
            self.mode = "LAND"
            return

        if self.disabled:
            self.mode = "DISABLED"
            self.speed = 0
            return

        if self.hold:
            self.mode = "HOLD"
            self.speed = 0
            return

        if self.returning:
            self.mode = "RTL"
            # Move towards base
            self._move_toward(BASE_LAT, BASE_LON, dt)
            dist = self._distance(BASE_LAT, BASE_LON)
            if dist < 5:
                self.returning = False
                self.mode = "LANDED"
                self.armed = False
            return

        # Normal flight: follow waypoints with formation offset
        self.mode = "AUTO"
        wps = self.waypoints or waypoints
        if wps:
            if self.role == "LEADER":
                target = wps[self.wp_idx % len(wps)]
                self._move_toward(target[0], target[1], dt)
                dist = self._distance(target[0], target[1])
                if dist < 5:
                    self.wp_idx = (self.wp_idx + 1) % len(wps)
            else:
                # Follow leader with offset
                off = FORMATION_OFFSETS.get(self.role, (0, 0))
                lat_off = off[1] / 111_320
                lon_off = off[0] / (111_320 * math.cos(math.radians(leader_pos[0])))
                target_lat = leader_pos[0] + lat_off
                target_lon = leader_pos[1] + lon_off
                self._move_toward(target_lat, target_lon, dt)

        # Altitude jitter
        self.altitude += random.uniform(-0.3, 0.3)
        self.altitude = max(10, min(120, self.altitude))

    def _move_toward(self, target_lat, target_lon, dt):
        dlat = target_lat - self.lat
        dlon = target_lon - self.lon
        dist = math.sqrt(dlat ** 2 + dlon ** 2) * 111_320
        if dist < 0.5:
            return
        ratio = min(1, (self.speed * dt) / dist)
        self.lat += dlat * ratio
        self.lon += dlon * ratio
        self.heading = math.degrees(math.atan2(dlon, dlat)) % 360

    def _distance(self, target_lat, target_lon):
        return math.sqrt((target_lat - self.lat) ** 2 + (target_lon - self.lon) ** 2) * 111_320

    def telemetry(self):
        return {
            "drone_id": self.drone_id,
            "latitude": round(self.lat, 7),
            "longitude": round(self.lon, 7),
            "altitude_m": round(self.altitude, 1),
            "battery_pct": round(self.battery, 1),
            "speed_mps": round(self.speed, 1),
            "velocity_mps": round(self.speed, 1),
            "heading_deg": round(self.heading, 1),
            "status": self.status,
            "mode": self.mode,
            "armed": self.armed,
            "mission_role": self.role,
            "gps_fix": self.gps_fix,
            "satellites_visible": self.satellites,
            "velocity": round(self.speed, 1),
            "timestamp": time.time(),
        }


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------
class SwarmSimulator:
    def __init__(self, num_drones=12, broker=MQTT_HOST, port=MQTT_PORT):
        self.num_drones = max(1, min(num_drones, 17))
        self.drones: dict[str, SimDrone] = {}
        self.running = False
        self._lock = threading.Lock()

        # Default patrol waypoints (square around base)
        self.waypoints = [
            (BASE_LAT + 0.002, BASE_LON),
            (BASE_LAT + 0.002, BASE_LON + 0.002),
            (BASE_LAT, BASE_LON + 0.002),
            (BASE_LAT, BASE_LON),
        ]

        # MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.broker = broker
        self.port = port

        # Create drones
        for i in range(self.num_drones):
            role = DEFAULT_ROLES[i % len(DEFAULT_ROLES)]
            d = SimDrone(i + 1, role, self.num_drones)
            self.drones[d.drone_id] = d

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"SwarmSim MQTT connected (rc={rc})")
        # Subscribe to commands; filter SIM- in handler
        client.subscribe("fleet/+/command")

    def _on_message(self, client, userdata, msg):
        """Handle incoming commands from Mission Control."""
        try:
            payload = json.loads(msg.payload.decode())
            drone_id = payload.get("drone_id")
            command = payload.get("command", "").upper()
            cmd_id = payload.get("cmd_id")

            if drone_id not in self.drones:
                return

            # Simulate command latency
            delay = random.uniform(0.1, 0.3)
            threading.Timer(delay, self._process_command, args=(drone_id, command, cmd_id, payload)).start()

        except Exception as e:
            print(f"SwarmSim command error: {e}")

    def _process_command(self, drone_id, command, cmd_id, payload):
        """Process a command after simulated latency."""
        drone = self.drones.get(drone_id)
        if not drone:
            return

        # Simulate occasional failure
        if random.random() < SIM_FAIL_RATE:
            result = "FAILED"
        else:
            result = "SUCCESS"
            with self._lock:
                if command == "HOLD":
                    drone.hold = True
                    drone.returning = False
                elif command == "RETURN":
                    drone.returning = True
                    drone.hold = False
                elif command == "DISABLE":
                    drone.disabled = True
                    drone.status = "DISABLED"
                elif command == "ENABLE":
                    drone.disabled = False
                    drone.status = "ACTIVE"
                    drone.mode = "AUTO"
                elif command == "ARM":
                    drone.armed = True
                elif command == "DISARM":
                    drone.armed = False
                    drone.mode = "DISARMED"
                elif command == "SET_ROLE":
                    drone.role = payload.get("role", drone.role)
                elif command == "UPLOAD_MISSION":
                    # Accept waypoints / geofence / asset_route
                    wps = payload.get("waypoints", [])
                    geofence = payload.get("geofence", [])
                    asset_route = payload.get("asset_route", [])
                    formation = payload.get("formation") or {}
                    if isinstance(formation, str):
                        formation = {"shape": formation, "spacing_m": 30}
                    spacing = formation.get("spacing_m")
                    if spacing:
                        FORMATION_OFFSETS["WINGMAN"] = (spacing, 0)
                        FORMATION_OFFSETS["SCOUT"] = (spacing * 2, 0)
                        FORMATION_OFFSETS["POINT_MAN"] = (0, spacing * 1.5)
                        FORMATION_OFFSETS["RELAY"] = (0, -spacing * 1.3)
                        FORMATION_OFFSETS["GUARD"] = (-spacing, 0)
                        FORMATION_OFFSETS["CARGO"] = (0, -spacing * 0.7)

                    if wps:
                        drone.waypoints = [(p["lat"], p["lon"]) if isinstance(p, dict) else (p[0], p[1]) for p in wps]
                        self.waypoints = drone.waypoints
                    elif geofence:
                        poly = [(p["lat"], p["lon"]) if isinstance(p, dict) else (p[0], p[1]) for p in geofence]
                        drone.waypoints = poly
                        self.waypoints = poly
                    elif asset_route:
                        route = [(p["lat"], p["lon"]) if isinstance(p, dict) else (p[0], p[1]) for p in asset_route]
                        drone.waypoints = route
                        self.waypoints = route
                    drone.hold = False
                    drone.returning = False
                    drone.disabled = False
                    drone.mode = "AUTO"
                elif command == "LAND":
                    drone.mode = "LAND"
                    drone.armed = False
                    drone.speed = 0

        # Publish ACK
        ack = {
            "cmd_id": cmd_id,
            "drone_id": drone_id,
            "command": command,
            "result": result,
            "timestamp": time.time(),
        }
        if "cmd_group_id" in payload:
            ack["cmd_group_id"] = payload["cmd_group_id"]

        self.client.publish("fleet/system/command_ack", json.dumps(ack))

    def _get_leader_pos(self):
        for d in self.drones.values():
            if d.role == "LEADER" and d.status == "ACTIVE":
                return (d.lat, d.lon)
        return (BASE_LAT, BASE_LON)

    def run(self):
        """Main simulation loop."""
        backoff = 1
        while True:
            try:
                self.client.connect(self.broker, self.port, 60)
                break
            except Exception as e:
                print(f"SwarmSim MQTT connect failed: {e}. Retry in {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

        self.client.loop_start()
        self.running = True

        hz = TELEMETRY_HZ if self.num_drones <= 15 else 0.5
        interval = 1.0 / hz
        print(f"SwarmSim running: {self.num_drones} drones at {hz} Hz, broker={self.broker}:{self.port}")

        oof_start = None  # out-of-formation tracking

        try:
            while self.running:
                tick_start = time.time()

                leader_pos = self._get_leader_pos()

                with self._lock:
                    for d in self.drones.values():
                        d.tick(interval, self.waypoints, leader_pos)

                # Publish telemetry
                for d in self.drones.values():
                    tel = d.telemetry()
                    jitter = random.uniform(-0.05, 0.05)
                    time.sleep(max(0, jitter))
                    self.client.publish(
                        f"fleet/{d.drone_id}/telemetry",
                        json.dumps(tel),
                    )

                # Check formation integrity (>40% OOF for >10s)
                active_count = sum(1 for d in self.drones.values() if d.status == "ACTIVE" and d.mode == "AUTO")
                total_assigned = len(self.drones)
                oof_pct = 1.0 - (active_count / max(total_assigned, 1))
                if oof_pct > 0.4:
                    if oof_start is None:
                        oof_start = time.time()
                    elif time.time() - oof_start > 10:
                        self.client.publish("fleet/system/event", json.dumps({
                            "type": "WARN",
                            "message": "FORMATION_COMPROMISED",
                            "oof_percent": round(oof_pct * 100, 1),
                            "timestamp": time.time(),
                        }))
                        oof_start = None  # reset after emitting
                else:
                    oof_start = None

                elapsed = time.time() - tick_start
                time.sleep(max(0, interval - elapsed))

        except KeyboardInterrupt:
            print("SwarmSim stopped")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="SwarmSim - Virtual drone fleet")
    parser.add_argument("--drones", type=int, default=12, help="Number of drones (1-17)")
    parser.add_argument("--broker", type=str, default=MQTT_HOST, help="MQTT broker host")
    parser.add_argument("--port", type=int, default=MQTT_PORT, help="MQTT broker port")
    args = parser.parse_args()

    sim = SwarmSimulator(num_drones=args.drones, broker=args.broker, port=args.port)
    sim.run()


if __name__ == "__main__":
    main()
