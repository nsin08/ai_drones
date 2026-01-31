"""
Mission Simulator: Demonstrates Mission v1 scenarios with real-time Grafana visualization.

Simulates PATROL, ESCORT, and PERIMETER_GUARD missions with drone formations
and publishes telemetry to MQTT for Grafana dashboard visualization.
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, asdict
from typing import List, Tuple
import paho.mqtt.client as mqtt


@dataclass
class DroneState:
    """Drone state for mission simulation."""
    drone_id: str
    mission_type: str  # PATROL, ESCORT, PERIMETER_GUARD
    mission_role: str  # LEADER, WINGMAN, POINT_MAN, SCOUT, RELAY
    lat: float
    lon: float
    altitude_m: float
    battery_pct: float
    velocity_mps: float
    mode: str
    mission_status: str
    fault_count: int = 0


class MissionSimulator:
    """Simulates drone missions with formation flying."""
    
    def __init__(self, mqtt_broker: str = "localhost", mqtt_port: int = 1883):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        self.mqtt_client.loop_start()
        
        # Mission parameters
        self.time_step = 0
        self.patrol_waypoints = [
            (28.6139, 77.2090),  # Delhi - start
            (28.6200, 77.2150),
            (28.6180, 77.2200),
            (28.6120, 77.2180),
        ]
        self.current_waypoint = 0
        
    def simulate_patrol_mission(self, duration_sec: int = 60):
        """Simulate PATROL mission with 5-drone formation."""
        print("\n🎯 Mission 1: PATROL")
        print("Objective: Follow route with multi-drone coverage")
        print("Formation: LEADER + POINT_MAN + 2x WINGMAN + SCOUT\n")
        
        drones = [
            DroneState("PATROL-01", "PATROL", "LEADER", 28.6139, 77.2090, 50.0, 100.0, 5.0, "AUTO", "IN_PROGRESS"),
            DroneState("PATROL-02", "PATROL", "POINT_MAN", 28.6145, 77.2095, 45.0, 100.0, 6.0, "AUTO", "IN_PROGRESS"),
            DroneState("PATROL-03", "PATROL", "WINGMAN", 28.6135, 77.2085, 50.0, 100.0, 5.0, "AUTO", "IN_PROGRESS"),
            DroneState("PATROL-04", "PATROL", "WINGMAN", 28.6135, 77.2095, 50.0, 100.0, 5.0, "AUTO", "IN_PROGRESS"),
            DroneState("PATROL-05", "PATROL", "SCOUT", 28.6130, 77.2080, 60.0, 100.0, 5.5, "AUTO", "IN_PROGRESS"),
        ]
        
        self._run_mission(drones, duration_sec, self._update_patrol)
        
    def simulate_escort_mission(self, duration_sec: int = 60):
        """Simulate ESCORT mission protecting a moving asset."""
        print("\n🎯 Mission 2: ESCORT")
        print("Objective: Protect moving asset with safety envelope")
        print("Formation: LEADER (on asset) + WINGMAN wedge + POINT_MAN + RELAY\n")
        
        drones = [
            DroneState("ESCORT-01", "ESCORT", "LEADER", 28.6139, 77.2090, 40.0, 100.0, 4.0, "AUTO", "IN_PROGRESS"),
            DroneState("ESCORT-02", "ESCORT", "WINGMAN", 28.6142, 77.2085, 40.0, 100.0, 4.0, "AUTO", "IN_PROGRESS"),
            DroneState("ESCORT-03", "ESCORT", "WINGMAN", 28.6142, 77.2095, 40.0, 100.0, 4.0, "AUTO", "IN_PROGRESS"),
            DroneState("ESCORT-04", "ESCORT", "POINT_MAN", 28.6150, 77.2090, 45.0, 100.0, 5.0, "AUTO", "IN_PROGRESS"),
            DroneState("ESCORT-05", "ESCORT", "RELAY", 28.6130, 77.2090, 55.0, 100.0, 3.0, "LOITER", "IN_PROGRESS"),
        ]
        
        self._run_mission(drones, duration_sec, self._update_escort)
        
    def simulate_perimeter_guard(self, duration_sec: int = 60):
        """Simulate PERIMETER_GUARD mission with sector coverage."""
        print("\n🎯 Mission 3: PERIMETER_GUARD")
        print("Objective: Maintain watch over fixed perimeter")
        print("Formation: LEADER (coordinator) + sector guards + roving POINT_MAN\n")
        
        # Perimeter center and radius
        center = (28.6139, 77.2090)
        radius = 0.005  # ~500m in degrees
        
        drones = [
            DroneState("GUARD-01", "PERIMETER_GUARD", "LEADER", center[0], center[1], 70.0, 100.0, 2.0, "LOITER", "IN_PROGRESS"),
            DroneState("GUARD-02", "PERIMETER_GUARD", "WINGMAN", center[0] + radius, center[1], 50.0, 100.0, 1.0, "LOITER", "IN_PROGRESS"),
            DroneState("GUARD-03", "PERIMETER_GUARD", "WINGMAN", center[0], center[1] + radius, 50.0, 100.0, 1.0, "LOITER", "IN_PROGRESS"),
            DroneState("GUARD-04", "PERIMETER_GUARD", "SCOUT", center[0] - radius, center[1], 50.0, 100.0, 1.0, "LOITER", "IN_PROGRESS"),
            DroneState("GUARD-05", "PERIMETER_GUARD", "POINT_MAN", center[0], center[1] - radius, 55.0, 100.0, 3.0, "AUTO", "IN_PROGRESS"),
        ]
        
        self._run_mission(drones, duration_sec, self._update_perimeter)
        
    def _run_mission(self, drones: List[DroneState], duration_sec: int, update_func):
        """Run mission simulation loop."""
        start_time = time.time()
        iteration = 0
        
        while (time.time() - start_time) < duration_sec:
            # Update drone positions
            update_func(drones, iteration)
            
            # Publish telemetry for each drone
            for drone in drones:
                self._publish_telemetry(drone)
            
            # Inject random faults occasionally
            if iteration % 20 == 0 and random.random() < 0.3:
                affected = random.choice(drones)
                affected.fault_count += 1
                affected.battery_pct = max(0, affected.battery_pct - random.uniform(5, 15))
                print(f"  ⚠️  Fault injected on {affected.drone_id}: battery dropped to {affected.battery_pct:.1f}%")
            
            # Battery drain
            for drone in drones:
                drone.battery_pct = max(0, drone.battery_pct - 0.1)
            
            iteration += 1
            time.sleep(1)
        
        print(f"\n✅ Mission completed: {duration_sec}s elapsed")
        
    def _update_patrol(self, drones: List[DroneState], iteration: int):
        """Update positions for PATROL mission."""
        # LEADER follows waypoints
        leader = drones[0]
        target = self.patrol_waypoints[self.current_waypoint % len(self.patrol_waypoints)]
        
        # Move toward waypoint
        dx = target[0] - leader.lat
        dy = target[1] - leader.lon
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist < 0.0005:  # ~50m
            self.current_waypoint += 1
            print(f"  📍 Waypoint {self.current_waypoint} reached")
        else:
            step = 0.0001  # ~10m per second
            leader.lat += (dx / dist) * step
            leader.lon += (dy / dist) * step
        
        # POINT_MAN runs ahead
        drones[1].lat = leader.lat + 0.0006
        drones[1].lon = leader.lon + 0.0005
        
        # WINGMAN formation (flanks)
        drones[2].lat = leader.lat - 0.0004
        drones[2].lon = leader.lon - 0.0005
        drones[3].lat = leader.lat - 0.0004
        drones[3].lon = leader.lon + 0.0005
        
        # SCOUT sweeps perimeter
        angle = (iteration * 0.1) % (2 * math.pi)
        drones[4].lat = leader.lat + 0.001 * math.cos(angle)
        drones[4].lon = leader.lon + 0.001 * math.sin(angle)
        
    def _update_escort(self, drones: List[DroneState], iteration: int):
        """Update positions for ESCORT mission."""
        # Asset moves forward (simulated)
        asset_lat = 28.6139 + (iteration * 0.00015)
        asset_lon = 77.2090 + (iteration * 0.00010)
        
        # LEADER tracks asset
        drones[0].lat = asset_lat
        drones[0].lon = asset_lon
        
        # WINGMAN wedge formation
        drones[1].lat = asset_lat + 0.0003
        drones[1].lon = asset_lon - 0.0003
        drones[2].lat = asset_lat + 0.0003
        drones[2].lon = asset_lon + 0.0003
        
        # POINT_MAN probes ahead
        drones[3].lat = asset_lat + 0.0010
        drones[3].lon = asset_lon
        
        # RELAY maintains comms anchor
        drones[4].lat = asset_lat - 0.0005
        drones[4].lon = asset_lon
        
    def _update_perimeter(self, drones: List[DroneState], iteration: int):
        """Update positions for PERIMETER_GUARD mission."""
        center = (28.6139, 77.2090)
        radius = 0.005
        
        # LEADER stays at center
        drones[0].lat = center[0]
        drones[0].lon = center[1]
        
        # Sector guards rotate slowly
        angle_offset = (iteration * 0.05) % (2 * math.pi)
        for i, drone in enumerate(drones[1:4], start=1):
            angle = (i * 2 * math.pi / 3) + angle_offset
            drone.lat = center[0] + radius * math.cos(angle)
            drone.lon = center[1] + radius * math.sin(angle)
        
        # POINT_MAN roves the boundary
        angle = (iteration * 0.2) % (2 * math.pi)
        drones[4].lat = center[0] + radius * math.cos(angle)
        drones[4].lon = center[1] + radius * math.sin(angle)
        
    def _publish_telemetry(self, drone: DroneState):
        """Publish drone telemetry to MQTT."""
        payload = {
            "drone_id": drone.drone_id,
            "mission_type": drone.mission_type,
            "mission_role": drone.mission_role,
            "lat": drone.lat,
            "lon": drone.lon,
            "altitude_m": drone.altitude_m,
            "battery_pct": drone.battery_pct,
            "velocity_mps": drone.velocity_mps,
            "mode": drone.mode,
            "mission_status": drone.mission_status,
            "fault_count": drone.fault_count,
            "timestamp": time.time()
        }
        
        topic = f"fleet/{drone.drone_id}/telemetry"
        self.mqtt_client.publish(topic, json.dumps(payload))
        
    def cleanup(self):
        """Stop MQTT client."""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Drone Fleet Mission Simulator")
    parser.add_argument("--mission", choices=["patrol", "escort", "perimeter", "all"], 
                       default="all", help="Mission type to simulate")
    parser.add_argument("--duration", type=int, default=60, 
                       help="Duration of each mission in seconds")
    parser.add_argument("--broker", default="localhost", 
                       help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, 
                       help="MQTT broker port")
    args = parser.parse_args()
    
    print("=" * 70)
    print("🚁 DRONE FLEET MISSION SIMULATOR")
    print("=" * 70)
    print(f"MQTT Broker: {args.broker}:{args.port}")
    print(f"Grafana Dashboard: http://localhost:3000")
    print(f"Mission Duration: {args.duration}s per mission")
    print("=" * 70)
    
    simulator = MissionSimulator(args.broker, args.port)
    
    try:
        if args.mission in ["patrol", "all"]:
            simulator.simulate_patrol_mission(args.duration)
            if args.mission == "all":
                time.sleep(5)
        
        if args.mission in ["escort", "all"]:
            simulator.simulate_escort_mission(args.duration)
            if args.mission == "all":
                time.sleep(5)
        
        if args.mission in ["perimeter", "all"]:
            simulator.simulate_perimeter_guard(args.duration)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Simulation stopped by user")
    finally:
        simulator.cleanup()
        print("\n✅ Cleanup complete")


if __name__ == "__main__":
    main()
