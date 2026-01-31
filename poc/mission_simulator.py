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
    status: str = "ACTIVE"  # ACTIVE or DISABLED


class MissionSimulator:
    """Simulates drone missions with formation flying."""
    
    def __init__(self, mqtt_broker: str = "localhost", mqtt_port: int = 1883):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self._on_command_message
        self.mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        self.mqtt_client.subscribe("fleet/+/command")
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
        self.current_drones = []  # Track active mission drones
        
    def _on_command_message(self, client, userdata, msg):
        """Handle command messages from mission control."""
        try:
            drone_id = msg.topic.split('/')[1]
            command_data = json.loads(msg.payload.decode())
            command = command_data.get('command')
            
            # Find the drone in current mission
            drone = next((d for d in self.current_drones if d.drone_id == drone_id), None)
            if not drone:
                return
            
            if command == 'DISABLE':
                print(f"\n⚠️  Command received: DISABLE {drone_id}")
                was_leader = drone.mission_role == 'LEADER'
                drone.status = 'DISABLED'
                drone.mode = 'LAND'
                self._publish_status(drone)
                
                if was_leader:
                    self._elect_new_leader(drone.mission_type)
                    
            elif command == 'ENABLE':
                print(f"\n✅ Command received: ENABLE {drone_id}")
                drone.status = 'ACTIVE'
                drone.mode = 'AUTO'
                self._publish_status(drone)
                
        except Exception as e:
            print(f"Error processing command: {e}")
    
    def _elect_new_leader(self, mission_type: str):
        """Elect a new leader when current leader is disabled."""
        # Find all active drones in this mission
        active_drones = [d for d in self.current_drones 
                        if d.mission_type == mission_type and d.status == 'ACTIVE' and d.mission_role != 'LEADER']
        
        if not active_drones:
            print("  ❌ No active drones available for leader election")
            return
        
        # Find old leader
        old_leader = next((d for d in self.current_drones if d.mission_role == 'LEADER' and d.mission_type == mission_type), None)
        
        # Elect drone with highest battery
        new_leader = max(active_drones, key=lambda d: d.battery_pct)
        old_role = new_leader.mission_role
        new_leader.mission_role = 'LEADER'
        
        print(f"  🎯 Leader election: {new_leader.drone_id} (battery: {new_leader.battery_pct:.1f}%) promoted from {old_role} to LEADER")
        
        # Publish leader election event
        event = {
            'mission_type': mission_type,
            'old_leader': old_leader.drone_id if old_leader else None,
            'new_leader': new_leader.drone_id,
            'reason': 'LEADER_DISABLED',
            'battery_pct': new_leader.battery_pct,
            'timestamp': time.time()
        }
        self.mqtt_client.publish(f"fleet/system/leader_election", json.dumps(event))
        self._publish_status(new_leader)
    
    def _publish_status(self, drone: DroneState):
        """Publish drone status change to MQTT."""
        payload = {
            'drone_id': drone.drone_id,
            'status': drone.status,
            'mission_role': drone.mission_role,
            'mode': drone.mode,
            'timestamp': time.time()
        }
        topic = f"fleet/{drone.drone_id}/status"
        self.mqtt_client.publish(topic, json.dumps(payload))
        self.current_drones = []  # Track active mission drones
        
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
        self.current_drones = drones  # Store for command handling
        start_time = time.time()
        iteration = 0
        
        while (time.time() - start_time) < duration_sec:
            # Update drone positions (only for active drones)
            active_drones = [d for d in drones if d.status == 'ACTIVE']
            update_func(active_drones, iteration)
            
            # Publish telemetry for ALL drones (including disabled)
            for drone in drones:
                self._publish_telemetry(drone)
            
            # Inject random faults occasionally (only on active drones)
            if iteration % 20 == 0 and random.random() < 0.3 and active_drones:
                affected = random.choice(active_drones)
                affected.fault_count += 1
                affected.battery_pct = max(0, affected.battery_pct - random.uniform(5, 15))
                print(f"  ⚠️  Fault injected on {affected.drone_id}: battery dropped to {affected.battery_pct:.1f}%")
            
            # Battery drain (all drones)
            for drone in drones:
                if drone.status == 'ACTIVE':
                    drone.battery_pct = max(0, drone.battery_pct - 0.1)
            
            iteration += 1
            time.sleep(1)
        
        print(f"\n✅ Mission completed: {duration_sec}s elapsed")
        
    def _update_patrol(self, drones: List[DroneState], iteration: int):
        """Update positions for PATROL mission."""
        if not drones:
            return
            
        # LEADER follows waypoints
        leader = next((d for d in drones if d.mission_role == 'LEADER'), drones[0])
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
        
        # Formation follows leader
        for drone in drones:
            if drone.drone_id == leader.drone_id:
                continue
                
            if 'POINT' in drone.mission_role:
                # POINT_MAN runs ahead
                drone.lat = leader.lat + 0.0006
                drone.lon = leader.lon + 0.0005
            elif 'WINGMAN' in drone.mission_role:
                # WINGMAN formation (flanks)
                offset = 1 if drones.index(drone) % 2 == 0 else -1
                drone.lat = leader.lat - 0.0004
                drone.lon = leader.lon + (0.0005 * offset)
            elif 'SCOUT' in drone.mission_role:
                # SCOUT sweeps perimeter
                angle = (iteration * 0.1) % (2 * math.pi)
                drone.lat = leader.lat + 0.001 * math.cos(angle)
                drone.lon = leader.lon + 0.001 * math.sin(angle)
        
    def _update_escort(self, drones: List[DroneState], iteration: int):
        """Update positions for ESCORT mission."""
        if not drones:
            return
            
        # Asset moves forward (simulated)
        asset_lat = 28.6139 + (iteration * 0.00015)
        asset_lon = 77.2090 + (iteration * 0.00010)
        
        # Find leader
        leader = next((d for d in drones if d.mission_role == 'LEADER'), drones[0])
        
        # LEADER tracks asset
        leader.lat = asset_lat
        leader.lon = asset_lon
        
        # Formation follows asset
        wingman_count = 0
        for drone in drones:
            if drone.drone_id == leader.drone_id:
                continue
                
            if 'WINGMAN' in drone.mission_role:
                # WINGMAN wedge formation
                offset = 1 if wingman_count % 2 == 0 else -1
                drone.lat = asset_lat + 0.0003
                drone.lon = asset_lon + (0.0003 * offset)
                wingman_count += 1
            elif 'POINT' in drone.mission_role:
                # POINT_MAN probes ahead
                drone.lat = asset_lat + 0.0010
                drone.lon = asset_lon
            elif 'RELAY' in drone.mission_role:
                # RELAY maintains comms anchor
                drone.lat = asset_lat - 0.0005
                drone.lon = asset_lon
        
    def _update_perimeter(self, drones: List[DroneState], iteration: int):
        """Update positions for PERIMETER_GUARD mission."""
        if not drones:
            return
            
        center = (28.6139, 77.2090)
        radius = 0.005
        
        # Find leader
        leader = next((d for d in drones if d.mission_role == 'LEADER'), None)
        if leader:
            # LEADER stays at center
            leader.lat = center[0]
            leader.lon = center[1]
        
        # Position other drones
        guard_index = 0
        for drone in drones:
            if drone.mission_role == 'LEADER':
                continue
                
            if 'WINGMAN' in drone.mission_role or 'SCOUT' in drone.mission_role:
                # Sector guards rotate slowly
                angle_offset = (iteration * 0.05) % (2 * math.pi)
                angle = (guard_index * 2 * math.pi / 3) + angle_offset
                drone.lat = center[0] + radius * math.cos(angle)
                drone.lon = center[1] + radius * math.sin(angle)
                guard_index += 1
            elif 'POINT' in drone.mission_role:
                # POINT_MAN roves the boundary
                angle = (iteration * 0.2) % (2 * math.pi)
                drone.lat = center[0] + radius * math.cos(angle)
                drone.lon = center[1] + radius * math.sin(angle)
        
    def _publish_telemetry(self, drone: DroneState):
        """Publish drone telemetry to MQTT."""
        payload = {
            "drone_id": drone.drone_id,
            "mission_type": drone.mission_type,
            "mission_role": drone.mission_role,
            "latitude": drone.lat,  # Changed from lat to latitude for consistency
            "longitude": drone.lon,  # Changed from lon to longitude
            "altitude_m": drone.altitude_m,
            "battery_pct": drone.battery_pct,
            "velocity_mps": drone.velocity_mps,
            "mode": drone.mode,
            "mission_status": drone.mission_status,
            "fault_count": drone.fault_count,
            "status": drone.status,
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
