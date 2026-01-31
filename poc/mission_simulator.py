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
            (28.6139, 77.2090),  # WP1 (Base)
            (28.6200, 77.2150),  # WP2 (North)
            (28.6180, 77.2200),  # WP3 (East)
            (28.6100, 77.2080),  # WP4 (South)
        ]
        self.escort_waypoints = [
            (28.6139, 77.2090),  # Escort start
            (28.6180, 77.2140),  # Escort middle
            (28.6160, 77.2180),  # Escort end
        ]
        self.current_waypoint = 0
        self.current_escort_waypoint = 0
        self.current_drones = []  # Track active mission drones
        
    def _on_command_message(self, client, userdata, msg):
        """Handle command messages from mission control."""
        try:
            drone_id = msg.topic.split('/')[1]
            command_data = json.loads(msg.payload.decode())
            command = command_data.get('command')
            cmd_id = command_data.get('cmd_id')
            
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
                
                # Send acknowledgment
                self._publish_command_ack(cmd_id, drone_id, command, 'SUCCESS')
                    
            elif command == 'ENABLE':
                print(f"\n✅ Command received: ENABLE {drone_id}")
                drone.status = 'ACTIVE'
                drone.mode = 'AUTO'
                self._publish_status(drone)
                
                # Send acknowledgment
                self._publish_command_ack(cmd_id, drone_id, command, 'SUCCESS')
            
            elif command == 'RETURN':
                print(f"\n🏠 Command received: RETURN TO BASE {drone_id}")
                drone.mode = 'RTL'  # Return to launch
                # Start moving drone back to base
                drone.latitude = 28.6139
                drone.longitude = 77.2090
                self._publish_status(drone)
                
                # Send acknowledgment
                self._publish_command_ack(cmd_id, drone_id, command, 'SUCCESS')
            
            elif command == 'HOLD':
                print(f"\n✋ Command received: HOLD POSITION {drone_id}")
                drone.mode = 'HOLD'
                self._publish_status(drone)
                
                # Send acknowledgment
                self._publish_command_ack(cmd_id, drone_id, command, 'SUCCESS')
                
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
    
    def _publish_command_ack(self, cmd_id: str, drone_id: str, command: str, result: str):
        """Publish command acknowledgment to MQTT."""
        payload = {
            'cmd_id': cmd_id,
            'drone_id': drone_id,
            'command': command,
            'result': result,
            'timestamp': time.time()
        }
        topic = "fleet/system/command_ack"
        self.mqtt_client.publish(topic, json.dumps(payload))
        
    def simulate_patrol_mission(self, duration_sec: int = 60, num_drones: int = 5):
        """Simulate PATROL mission with configurable drone count."""
        print("\n🎯 Mission 1: PATROL")
        print(f"Objective: Follow route with {num_drones}-drone coverage")
        print("Formation: LEADER + formation based on count\n")
        
        # Define roles based on drone count
        roles = ["LEADER", "POINT_MAN", "WINGMAN", "WINGMAN", "SCOUT", 
                 "WINGMAN", "WINGMAN", "SCOUT", "RELAY", "RELAY", "GUARD", "GUARD"]
        
        drones = []
        for i in range(min(num_drones, 12)):
            drones.append(DroneState(
                f"PATROL-{i+1:02d}", 
                "PATROL", 
                roles[i],
                28.6139 + (i * 0.0005), 
                77.2090 + (i * 0.0005), 
                50.0 + (i * 2), 
                100.0, 
                5.0, 
                "AUTO", 
                "IN_PROGRESS"
            ))
        
        self._run_mission(drones, duration_sec, self._update_patrol)
        
    def simulate_escort_mission(self, duration_sec: int = 60, num_drones: int = 5):
        """Simulate ESCORT mission protecting a moving asset."""
        print("\n🎯 Mission 2: ESCORT")
        print(f"Objective: Protect moving asset with {num_drones} drones")
        print("Formation: LEADER (on asset) + protective envelope\n")
        
        roles = ["LEADER", "WINGMAN", "WINGMAN", "POINT_MAN", "RELAY",
                 "WINGMAN", "WINGMAN", "GUARD", "GUARD", "RELAY", "SCOUT", "SCOUT"]
        
        drones = []
        for i in range(min(num_drones, 12)):
            drones.append(DroneState(
                f"ESCORT-{i+1:02d}",
                "ESCORT",
                roles[i],
                28.6139 + (i * 0.0004),
                77.2090 + (i * 0.0004),
                40.0 + (i * 2),
                100.0,
                4.0,
                "AUTO",
                "IN_PROGRESS"
            ))
        
        self._run_mission(drones, duration_sec, self._update_escort)
        
    def simulate_perimeter_guard(self, duration_sec: int = 60, num_drones: int = 5):
        """Simulate PERIMETER_GUARD mission with sector coverage."""
        print("\n🎯 Mission 3: PERIMETER_GUARD")
        print(f"Objective: Maintain watch over fixed perimeter with {num_drones} drones")
        print("Formation: LEADER (coordinator) + sector guards\n")
        
        # Perimeter center and radius
        center = (28.6139, 77.2090)
        radius = 0.005  # ~500m in degrees
        
        roles = ["LEADER", "WINGMAN", "WINGMAN", "SCOUT", "POINT_MAN",
                 "GUARD", "GUARD", "SCOUT", "WINGMAN", "RELAY", "RELAY", "POINT_MAN"]
        
        drones = []
        for i in range(min(num_drones, 12)):
            # Position drones around perimeter
            angle = (i * 2 * 3.14159) / num_drones
            lat_offset = radius * math.cos(angle)
            lon_offset = radius * math.sin(angle)
            
            drones.append(DroneState(
                f"GUARD-{i+1:02d}",
                "PERIMETER_GUARD",
                roles[i],
                center[0] + lat_offset,
                center[1] + lon_offset,
                50.0 + (i * 2),
                100.0,
                1.0 if i == 0 else 2.0,
                "LOITER" if i == 0 else "AUTO",
                "IN_PROGRESS"
            ))
        
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
            
        # Asset follows escort waypoints
        target = self.escort_waypoints[self.current_escort_waypoint % len(self.escort_waypoints)]
        
        # Find leader
        leader = next((d for d in drones if d.mission_role == 'LEADER'), drones[0])
        
        # Move asset (and LEADER) toward waypoint
        dx = target[0] - leader.lat
        dy = target[1] - leader.lon
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist < 0.0005:  # ~50m
            self.current_escort_waypoint += 1
        
        # LEADER tracks asset - move smoothly toward waypoint
        if dist > 0.00001:
            leader.lat += dx * 0.1
            leader.lon += dy * 0.1
        else:
            leader.lat = target[0]
            leader.lon = target[1]
        
        # Formation follows asset
        wingman_count = 0
        for drone in drones:
            if drone.drone_id == leader.drone_id:
                continue
                
            if 'WINGMAN' in drone.mission_role:
                # WINGMAN wedge formation
                offset = 1 if wingman_count % 2 == 0 else -1
                drone.lat = leader.lat + 0.0003
                drone.lon = leader.lon + (0.0003 * offset)
                wingman_count += 1
            elif 'POINT' in drone.mission_role:
                # POINT_MAN probes ahead
                drone.lat = leader.lat + 0.0010
                drone.lon = leader.lon
            elif 'RELAY' in drone.mission_role:
                # RELAY maintains comms anchor
                drone.lat = leader.lat - 0.0005
                drone.lon = leader.lon
        
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
    parser.add_argument("--drones", type=int, default=5,
                       help="Number of drones (1-12)")
    parser.add_argument("--broker", default="localhost", 
                       help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, 
                       help="MQTT broker port")
    args = parser.parse_args()
    
    # Clamp drone count to valid range
    drone_count = max(1, min(12, args.drones))
    
    print("=" * 70)
    print("🚁 DRONE FLEET MISSION SIMULATOR")
    print("=" * 70)
    print(f"MQTT Broker: {args.broker}:{args.port}")
    print(f"Grafana Dashboard: http://localhost:3000")
    print(f"Mission Duration: {args.duration}s per mission")
    print(f"Drone Count: {drone_count}")
    print("=" * 70)
    
    simulator = MissionSimulator(args.broker, args.port)
    
    try:
        if args.mission in ["patrol", "all"]:
            simulator.simulate_patrol_mission(args.duration, num_drones=drone_count)
            if args.mission == "all":
                time.sleep(5)
        
        if args.mission in ["escort", "all"]:
            simulator.simulate_escort_mission(args.duration, num_drones=drone_count)
            if args.mission == "all":
                time.sleep(5)
        
        if args.mission in ["perimeter", "all"]:
            simulator.simulate_perimeter_guard(args.duration, num_drones=drone_count)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Simulation stopped by user")
    finally:
        simulator.cleanup()
        print("\n✅ Cleanup complete")


if __name__ == "__main__":
    main()
