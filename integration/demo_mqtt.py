#!/usr/bin/env python3
"""Integration demo: Real MQTT broker with fault injection.

This demo simulates:
1. Fleet simulator publishing telemetry to MQTT
2. Fault injector modifying telemetry
3. Mission Planner subscribing to telemetry (via MQTT.Cool)
4. AI advisory recommending actions

Run FIRST:
  cd ops
  docker-compose up -d

Then:
  cd poc
  python ../integration/demo_mqtt.py
"""

import json
import time
import sys
import argparse
from pathlib import Path

# Add poc to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "poc"))

from src.domain.telemetry import Telemetry, Position
from src.domain.fault_registry import FaultModelRegistry
from src.domain.rf_loss_burst import RFLossBurstFault
from src.domain.gnss_multipath import GNSSMultipathFault
from src.domain.ekf_unhealthy import EKFUnhealthyFault
from src.domain.thrust_shortfall import ThrustShortfallFault
from src.domain.battery_sag import BatterySagFault
from src.adapters.mqtt_broker import MQTTBrokerAdapter


def run_mqtt_demo(
    broker_host: str = "localhost",
    broker_port: int = 1883,
    num_messages: int = 50,
    message_interval: float = 0.5
):
    """Run full MQTT integration demo.
    
    Args:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port
        num_messages: Number of telemetry messages to send
        message_interval: Delay between messages (seconds)
    """
    
    print("\n" + "="*70)
    print("[MQTT Demo] Drone Fleet Ops MVP - Integration Test")
    print("="*70)
    
    # Initialize MQTT adapter
    print(f"\n[Setup] Connecting to MQTT broker at {broker_host}:{broker_port}...")
    broker = MQTTBrokerAdapter(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id="fleet-simulator"
    )
    
    if not broker.connect():
        print("[ERROR] Failed to connect to MQTT broker!")
        print("\nMake sure to start the broker first:")
        print("  cd ops && docker-compose up -d")
        sys.exit(1)
    
    print("[Setup] ✅ Connected to MQTT broker")
    
    # Initialize fault registry
    print("[Setup] Initializing fault models...")
    registry = FaultModelRegistry()
    registry.register("RF_LOSS_BURST", RFLossBurstFault)
    registry.register("GNSS_MULTIPATH", GNSSMultipathFault)
    registry.register("EKF_UNHEALTHY", EKFUnhealthyFault)
    registry.register("THRUST_SHORTFALL", ThrustShortfallFault)
    registry.register("BATTERY_SAG", BatterySagFault)
    print(f"[Setup] ✅ Registered {len(registry.list_registered())} fault models: {', '.join(registry.list_registered())}")
    
    # Create fault instance
    fault = registry.create(
        "RF_LOSS_BURST",
        every_sec=15.0,  # Burst every 15 seconds
        down_sec=5.0     # Lasts 5 seconds
    )
    
    # Setup subscription to monitor commands (from Mission Planner)
    received_commands = []
    
    def on_command(topic: str, payload: str):
        try:
            cmd = json.loads(payload)
            received_commands.append(cmd)
            print(f"\n[Command] Received on {topic}:")
            print(f"  {json.dumps(cmd, indent=2)}")
        except Exception as e:
            print(f"[Error] Failed to parse command: {e}")
    
    broker.subscribe("ai_drones/commands/D001/mission", on_command)
    broker.subscribe("ai_drones/commands/D001/rtl", on_command)
    
    print("[Setup] ✅ Subscribed to commands")
    
    # Simulate telemetry + faults
    print(f"\n[Simulation] Starting {num_messages} telemetry messages...")
    print("-" * 70)
    
    base_pos = Position(lat=28.6139, lon=77.2090, alt_m=50.0)
    stats = {"total": 0, "passed": 0, "dropped": 0, "published": 0}
    
    for msg_num in range(num_messages):
        # Create telemetry
        sim_time = msg_num * message_interval
        battery = 100.0 - (msg_num * 0.5)
        
        telemetry = Telemetry(
            drone_id="D001",
            timestamp=time.time(),
            position=base_pos,
            battery_pct=max(battery, 10.0),
            velocity_mps=15.0,
            armed=True,
            mode="GUIDED"
        )
        
        # Apply faults
        result, faults = fault.apply(telemetry)
        
        stats["total"] += 1
        
        # Publish to MQTT
        if result is not None:
            stats["passed"] += 1
            status = "✅ PASSED"
            
            # Publish successful telemetry
            payload = {
                "drone_id": result.drone_id,
                "timestamp": result.timestamp,
                "position": {
                    "lat": result.position.lat,
                    "lon": result.position.lon,
                    "alt_m": result.position.alt_m
                },
                "battery_pct": result.battery_pct,
                "velocity_mps": result.velocity_mps,
                "armed": result.armed,
                "mode": result.mode
            }
            
            success = broker.publish(
                f"ai_drones/telemetry/D001",
                json.dumps(payload)
            )
            if success:
                stats["published"] += 1
        else:
            stats["dropped"] += 1
            status = "❌ DROPPED"
            
            # Publish fault notification
            fault_payload = {
                "fault_type": faults[0] if faults else "UNKNOWN",
                "active": True,
                "drone_id": "D001",
                "timestamp": time.time()
            }
            broker.publish(
                f"ai_drones/faults/D001",
                json.dumps(fault_payload)
            )
        
        print(f"[{msg_num:03d}] t={sim_time:5.1f}s | Battery: {battery:5.1f}% | {status}")
        
        # Small delay between messages
        if msg_num < num_messages - 1:
            time.sleep(message_interval)
    
    # Summary
    print("\n" + "-" * 70)
    print("[Summary]")
    print(f"  Total messages: {stats['total']}")
    print(f"  Passed:         {stats['passed']} ({100*stats['passed']//stats['total']}%)")
    print(f"  Dropped:        {stats['dropped']} ({100*stats['dropped']//stats['total']}%)")
    print(f"  Published:      {stats['published']}")
    print(f"  Commands rcvd:  {len(received_commands)}")
    
    print("\n[MQTT Topics to Monitor in MQTT.Cool]")
    print("  Sub: ai_drones/# (all topics)")
    print("  Sub: ai_drones/telemetry/D001 (live telemetry)")
    print("  Sub: ai_drones/faults/D001 (fault notifications)")
    print("  Pub: ai_drones/commands/D001/mission (send commands)")
    
    print("\n[Fleet Services That Can Subscribe]")
    print("  ✓ Mission Planner: Receives telemetry + faults")
    print("  ✓ Planner: Subscribes to telemetry, publishes plans")
    print("  ✓ AI Advisory: Evaluates faults, publishes recommendations")
    
    # Cleanup
    print("\n[Cleanup] Disconnecting from MQTT...")
    broker.disconnect()
    print("[MQTT Demo] ✅ Complete!\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT integration demo")
    parser.add_argument(
        "--broker",
        default="localhost",
        help="MQTT broker hostname (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)"
    )
    parser.add_argument(
        "--messages",
        type=int,
        default=50,
        help="Number of telemetry messages (default: 50)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Delay between messages in seconds (default: 0.5)"
    )
    
    args = parser.parse_args()
    
    try:
        run_mqtt_demo(
            broker_host=args.broker,
            broker_port=args.port,
            num_messages=args.messages,
            message_interval=args.interval
        )
    except KeyboardInterrupt:
        print("\n[Interrupted]")
        sys.exit(0)
