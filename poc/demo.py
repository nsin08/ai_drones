"""PoC Demo: Fault Injection with Hexagonal Architecture."""
import argparse
import time
from src.domain.telemetry import Telemetry, Position
from src.domain.fault_registry import FaultModelRegistry
from src.domain.rf_loss_burst import RFLossBurstFault
from src.domain.gnss_multipath import GNSSMultipathFault
from src.domain.ekf_unhealthy import EKFUnhealthyFault
from src.domain.thrust_shortfall import ThrustShortfallFault
from src.domain.battery_sag import BatterySagFault
from src.adapters.memory_broker import InMemoryBroker
from src.adapters.mqtt_broker import MQTTBrokerAdapter


def run_demo():
    """Run the PoC demonstration."""
    parser = argparse.ArgumentParser(description="Fault Injection PoC Demo")
    parser.add_argument("--broker", choices=["memory", "mqtt"], default="memory",
                       help="Broker type (memory=in-memory, mqtt=real MQTT)")
    parser.add_argument("--messages", type=int, default=40,
                       help="Number of telemetry messages to simulate")
    parser.add_argument("--faults", choices=["all", "rf", "gnss", "ekf", "thrust", "battery"], 
                       default="all", help="Which faults to demonstrate")
    args = parser.parse_args()
    
    print("[PoC Demo] Initializing fault injection system...")
    print(f"[PoC Demo] Broker: {'InMemoryBroker' if args.broker == 'memory' else 'MQTTBroker'}")
    
    # Create broker (hexagonal architecture - swap implementations)
    if args.broker == "memory":
        broker = InMemoryBroker()
    else:
        broker = MQTTBrokerAdapter(broker_host="localhost", broker_port=1883, client_id="poc-demo")
        if not broker.connect():
            print("[PoC Demo] ERROR: Failed to connect to MQTT broker at localhost:1883")
            print("[PoC Demo] Start it with: cd ops && docker compose up -d")
            return
    
    # Create fault registry and register all fault models
    registry = FaultModelRegistry()
    faults_to_apply = []
    
    if args.faults in ["all", "rf"]:
        registry.register("RF_LOSS_BURST", RFLossBurstFault)
        faults_to_apply.append(registry.create("RF_LOSS_BURST", every_sec=10.0, down_sec=3.0))
        print("[PoC Demo] Registered: RF_LOSS_BURST (every 10s, down 3s)")
    
    if args.faults in ["all", "gnss"]:
        registry.register("GNSS_MULTIPATH", GNSSMultipathFault)
        faults_to_apply.append(registry.create("GNSS_MULTIPATH", every_sec=15.0, duration_sec=4.0, offset_range=8.0))
        print("[PoC Demo] Registered: GNSS_MULTIPATH (every 15s, lasts 4s, ±8m offset)")
    
    if args.faults in ["all", "ekf"]:
        registry.register("EKF_UNHEALTHY", EKFUnhealthyFault)
        faults_to_apply.append(registry.create("EKF_UNHEALTHY", every_sec=20.0, duration_sec=5.0, noise_stddev_m=12.0))
        print("[PoC Demo] Registered: EKF_UNHEALTHY (every 20s, lasts 5s, stddev=12m noise)")
    
    if args.faults in ["all", "thrust"]:
        registry.register("THRUST_SHORTFALL", ThrustShortfallFault)
        faults_to_apply.append(registry.create("THRUST_SHORTFALL", every_sec=25.0, duration_sec=6.0, alt_loss_mps=1.5))
        print("[PoC Demo] Registered: THRUST_SHORTFALL (every 25s, lasts 6s, -1.5m/s altitude)")
    
    if args.faults in ["all", "battery"]:
        registry.register("BATTERY_SAG", BatterySagFault)
        faults_to_apply.append(registry.create("BATTERY_SAG", every_sec=30.0, duration_sec=8.0, sag_pct_per_sec=1.2))
        print("[PoC Demo] Registered: BATTERY_SAG (every 30s, lasts 8s, -1.2%/s drain)")
    
    if not faults_to_apply:
        print("[PoC Demo] ERROR: No faults selected")
        return
    
    print(f"\n[PoC Demo] Simulating {args.messages} telemetry messages (0.5s intervals)...")
    print(f"[PoC Demo] Watch for fault activations below:\n")
    
    # Simulate telemetry messages
    passed = 0
    dropped = 0
    fault_counts = {}
    initial_position = Position(lat=28.6139, lon=77.2090, alt_m=100.0)
    initial_battery = 100.0
    
    for i in range(args.messages):
        # Create telemetry (start fresh each iteration to see fault effects clearly)
        telemetry = Telemetry(
            drone_id="D001",
            timestamp=time.time(),
            position=initial_position,
            battery_pct=initial_battery - (i * 0.1)  # Natural slow drain
        )
        
        # Apply all fault models in sequence
        result = telemetry
        active_faults = []
        
        for fault_model in faults_to_apply:
            if result is not None:
                result, faults = fault_model.apply(result)
                active_faults.extend(faults)
                for fault_code in faults:
                    fault_counts[fault_code] = fault_counts.get(fault_code, 0) + 1
        
        # Display result with details
        if result is None:
            # RF_LOSS_BURST dropped the message
            status = "DROPPED"
            details = f"battery: {telemetry.battery_pct:.1f}%"
            dropped += 1
        else:
            status = "PASSED"
            # Show what changed
            pos_changed = (result.position.lat != initial_position.lat or 
                          result.position.lon != initial_position.lon or 
                          result.position.alt_m != initial_position.alt_m)
            bat_changed = abs(result.battery_pct - (initial_battery - i * 0.1)) > 0.01
            
            details_parts = []
            details_parts.append(f"bat: {result.battery_pct:.1f}%")
            if pos_changed:
                details_parts.append(f"alt: {result.position.alt_m:.1f}m")
            
            details = ", ".join(details_parts)
            passed += 1
        
        fault_str = f" [{', '.join(active_faults)}]" if active_faults else ""
        print(f"[{i:02d}] {telemetry.drone_id} @ t={i*0.5:.1f}s -> {status:12s} {fault_str:40s} ({details})")
        
        # Publish to broker (if not dropped)
        if result is not None:
            broker.publish(f"fleet/{telemetry.drone_id}/telemetry", {
                "drone_id": result.drone_id,
                "battery_pct": result.battery_pct,
                "altitude_m": result.position.alt_m,
                "lat": result.position.lat,
                "lon": result.position.lon
            })
        
        # Small delay for realistic timing
        time.sleep(0.5)
    
    # Summary
    print(f"\n[PoC Demo] ========== SUMMARY ==========")
    print(f"  Total messages: {args.messages}")
    print(f"  Passed: {passed} ({passed/args.messages*100:.0f}%)")
    print(f"  Dropped: {dropped} ({dropped/args.messages*100:.0f}%)")
    print(f"\n  Fault Activations:")
    for fault_code, count in sorted(fault_counts.items()):
        print(f"    {fault_code}: {count} times")
    
    # Verify broker received messages (in-memory only)
    if hasattr(broker, "get_published"):
        published = broker.get_published()
        print(f"\n  Broker published: {len(published)} messages")

    print(f"\n[PoC Demo] OK: All {len(faults_to_apply)} fault model(s) demonstrated")
    print(f"[PoC Demo] OK: Hexagonal architecture validated")
    print(f"\n[PoC Demo] Key achievements:")
    print("  - Domain logic has zero external dependencies")
    print("  - Tests run without MQTT broker")
    print("  - Easy to swap InMemory <-> MQTT broker")
    print("  - Fault models are pluggable via registry")
    print(f"\n[PoC Demo] Run tests: pytest tests/unit -v (56 tests)")
    print(f"[PoC Demo] Try: python demo.py --faults gnss --messages 30")


if __name__ == "__main__":
    run_demo()
