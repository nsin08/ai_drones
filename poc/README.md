# PoC: Fault Injection with Hexagonal Architecture

**Goal:** Demonstrate TDD + Hexagonal + Registry + Strategy patterns in 2 hours

## What This PoC Demonstrates

1. **Hexagonal Architecture** - Domain logic independent of MQTT
2. **Strategy Pattern** - Pluggable fault models
3. **Registry Pattern** - Dynamic fault registration
4. **TDD** - Tests written before implementation
5. **Port/Adapter** - Swap InMemory ↔ MQTT brokers

## Structure

```
poc/
├── README.md           # This file
├── src/
│   ├── domain/         # Core business logic (no external deps)
│   │   ├── telemetry.py
│   │   ├── fault_model.py
│   │   ├── rf_loss_burst.py
│   │   └── fault_registry.py
│   ├── ports/
│   │   └── message_broker.py
│   ├── adapters/
│   │   ├── memory_broker.py
│   │   └── mqtt_broker.py
│   └── apps/
│       └── fault_injector.py
├── tests/
│   ├── unit/
│   │   ├── test_telemetry.py
│   │   ├── test_rf_loss_burst.py
│   │   └── test_fault_registry.py
│   └── integration/
│       └── test_fault_injector.py
└── demo.py             # Runnable demo

```

## Running the PoC

### 1. Install dependencies
```bash
cd poc
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install pytest paho-mqtt
```

### 2. Run tests (TDD verification)
```bash
pytest tests/unit -v
# Should show 100% pass rate
```

### 3. Run demo (without MQTT)
```bash
python demo.py --broker memory
# Uses InMemoryBroker - no Docker needed!
```

### 4. Run demo (with MQTT)
```bash
# Terminal 1: Start MQTT broker
docker compose -f ../../ops/docker-compose.yml up

# Terminal 2: Run demo
python demo.py --broker mqtt
```

## Expected Output

```
[PoC Demo] Initializing fault injection system...
[PoC Demo] Broker: InMemoryBroker
[PoC Demo] Registered fault: RF_LOSS_BURST

[PoC Demo] Simulating 20 telemetry messages...

[00] D001 @ t=0.0s   → ✅ PASSED (battery: 100.0%)
[01] D001 @ t=1.0s   → ✅ PASSED (battery: 99.8%)
[02] D001 @ t=2.0s   → ✅ PASSED (battery: 99.6%)
[03] D001 @ t=3.0s   → ❌ DROPPED (RF_LOSS_BURST active)
[04] D001 @ t=4.0s   → ❌ DROPPED (RF_LOSS_BURST active)
[05] D001 @ t=5.0s   → ❌ DROPPED (RF_LOSS_BURST active)
[06] D001 @ t=6.0s   → ✅ PASSED (burst ended)
...

[PoC Demo] Summary:
  Total messages: 20
  Passed: 15 (75%)
  Dropped: 5 (25%)
  Faults detected: RF_LOSS_BURST

[PoC Demo] ✅ Fault injection working!
[PoC Demo] ✅ Hexagonal architecture validated!
```

## Key Learning Points

### 1. Domain is Pure Python
```python
# src/domain/rf_loss_burst.py
# NO imports from paho-mqtt, json, or any I/O library!
# Only stdlib + domain types

class RFLossBurstFault(FaultModel):
    def apply(self, telemetry: Telemetry):
        # Pure logic - 100% testable without I/O
        pass
```

### 2. Tests Run Without MQTT
```python
# tests/unit/test_rf_loss_burst.py
def test_drops_message_during_burst():
    fault = RFLossBurstFault(every_sec=10, down_sec=3)
    telemetry = Telemetry(drone_id="D001", ...)
    
    # No MQTT broker needed!
    result, faults = fault.apply(telemetry)
    assert result is None
```

### 3. Easy to Swap Implementations
```python
# No MQTT? Use InMemoryBroker
broker = InMemoryBroker()

# Need MQTT? Swap in one line
broker = MQTTBrokerAdapter("localhost", 1883)

# Domain code unchanged!
injector = FaultInjector(broker, registry)
```

### 4. Add New Faults Easily
```python
# Just implement interface + register
class MyNewFault(FaultModel):
    def apply(self, telemetry):
        return telemetry, ["MY_FAULT"]

registry.register("MY_FAULT", MyNewFault)
# Done! No changes to injector
```

## Test Coverage

Run `pytest --cov=src --cov-report=html` to see coverage report.

**Target:**
- Domain layer: 100%
- Ports: 100%
- Adapters: 80%
- Apps: 60%

## Next Steps After PoC

1. ✅ Validated architecture works
2. Add remaining 4 faults (GNSS, EKF, thrust, battery)
3. Add MQTT adapter integration tests
4. Refactor existing `fault_injector.py` to use this architecture
5. Apply same pattern to planner + AI

## Time Breakdown

- Setup + first test: 15 min
- Telemetry entity (TDD): 20 min
- FaultModel interface: 10 min
- RFLossBurstFault (TDD): 30 min
- Registry (TDD): 20 min
- MessageBroker port + adapters: 25 min
- Demo script: 20 min
- **Total: ~2 hours**
