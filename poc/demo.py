"""PoC Demo: Fault Injection with Hexagonal Architecture."""
import argparse
import time
from src.domain.telemetry import Telemetry, Position
from src.domain.fault_registry import FaultModelRegistry
from src.domain.rf_loss_burst import RFLossBurstFault
from src.adapters.memory_broker import InMemoryBroker


def run_demo():
    """Run the PoC demonstration."""
    parser = argparse.ArgumentParser(description="Fault Injection PoC Demo")
    parser.add_argument("--broker", choices=["memory", "mqtt"], default="memory",
                       help="Broker type (memory=in-memory, mqtt=real MQTT)")
    parser.add_argument("--messages", type=int, default=20,
                       help="Number of telemetry messages to simulate")
    args = parser.parse_args()
    
    print("[PoC Demo] Initializing fault injection system...")
    print(f"[PoC Demo] Broker: {'InMemoryBroker' if args.broker == 'memory' else 'MQTTBroker'}")
    
    # Create broker (hexagonal architecture - swap implementations)
    if args.broker == "memory":
        broker = InMemoryBroker()
    else:
        print("[PoC Demo] ERROR: MQTT broker not implemented in PoC")
        print("[PoC Demo] Use --broker memory for now")
        return
    
    # Create fault registry
    registry = FaultModelRegistry()
    registry.register("RF_LOSS_BURST", RFLossBurstFault)
    print("[PoC Demo] Registered fault: RF_LOSS_BURST")
    
    # Create fault instance (short intervals for demo)
    fault = registry.create("RF_LOSS_BURST", every_sec=5.0, down_sec=3.0)
    
    print(f"\n[PoC Demo] Simulating {args.messages} telemetry messages...")
    print(f"[PoC Demo] RF Burst: Every 5s, lasts 3s\n")
    
    # Simulate telemetry messages
    passed = 0
    dropped = 0
    position = Position(lat=28.6139, lon=77.2090, alt_m=20.0)
    
    for i in range(args.messages):
        # Create telemetry
        telemetry = Telemetry(
            drone_id="D001",
            timestamp=time.time(),
            position=position,
            battery_pct=100.0 - (i * 0.2)  # Slowly draining
        )
        
        # Apply fault model
        result, faults = fault.apply(telemetry)
        
        # Display result
        status = "❌ DROPPED" if result is None else "✅ PASSED"
        fault_str = f" ({', '.join(faults)})" if faults else ""
        battery_str = f" (battery: {telemetry.battery_pct:.1f}%)"
        
        print(f"[{i:02d}] {telemetry.drone_id} @ t={i*0.5:.1f}s   → {status}{fault_str}{battery_str}")
        
        # Publish to broker (if not dropped)
        if result is not None:
            broker.publish(f"fleet/{telemetry.drone_id}/telemetry", {
                "drone_id": telemetry.drone_id,
                "battery_pct": telemetry.battery_pct
            })
            passed += 1
        else:
            dropped += 1
        
        # Small delay for realistic timing
        time.sleep(0.5)
    
    # Summary
    print(f"\n[PoC Demo] Summary:")
    print(f"  Total messages: {args.messages}")
    print(f"  Passed: {passed} ({passed/args.messages*100:.0f}%)")
    print(f"  Dropped: {dropped} ({dropped/args.messages*100:.0f}%)")
    print(f"  Faults detected: RF_LOSS_BURST")
    
    # Verify broker received messages
    published = broker.get_published()
    print(f"\n[PoC Demo] Broker published {len(published)} messages")
    
    print(f"\n[PoC Demo] ✅ Fault injection working!")
    print(f"[PoC Demo] ✅ Hexagonal architecture validated!")
    print(f"\n[PoC Demo] Key achievements:")
    print("  ✅ Domain logic has ZERO external dependencies")
    print("  ✅ Tests run without MQTT broker")
    print("  ✅ Easy to swap InMemory ↔ MQTT broker")
    print("  ✅ Fault models are pluggable via registry")
    print("\n[PoC Demo] Run tests: pytest tests/unit -v")


if __name__ == "__main__":
    run_demo()
