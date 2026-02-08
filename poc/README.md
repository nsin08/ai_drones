# PoC: Fault Injection + Fleet Telemetry (Hexagonal Architecture)

**Last reviewed:** February 1, 2026  
**Goal:** Demonstrate TDD + Hexagonal + Registry + Strategy patterns, plus a small end-to-end MQTT telemetry loop (simulator -> mission control UI).

## What This PoC Demonstrates

1. **Hexagonal Architecture** - Domain logic independent of MQTT
2. **Strategy Pattern** - Pluggable fault models
3. **Registry Pattern** - Dynamic fault registration
4. **TDD** - Tests written before implementation
5. **Port/Adapter** - Swap InMemory <-> MQTT brokers
6. **Fleet Telemetry Loop** - MQTT topics + a minimal Mission Control UI (Flask + Socket.IO)

## Structure

```
poc/
├── README.md                 # This file
├── QUICKSTART.md             # Short commands to run it
├── requirements.txt          # Minimal deps
├── src/
│   ├── domain/               # Pure domain logic (no I/O deps)
│   │   ├── telemetry.py
│   │   ├── fault_model.py
│   │   ├── fault_registry.py
│   │   ├── rf_loss_burst.py
│   │   ├── gnss_multipath.py
│   │   ├── ekf_unhealthy.py
│   │   ├── thrust_shortfall.py
│   │   └── battery_sag.py
│   ├── ports/
│   │   └── message_broker.py
│   └── adapters/
│       ├── memory_broker.py
│       └── mqtt_broker.py
├── tests/
│   └── unit/                 # Unit tests for domain + registry
├── demo.py                   # Fault-model demo runner (memory or MQTT)
├── mission_simulator.py       # Publishes telemetry to MQTT (fleet/*)
├── mission_control.py         # Flask UI + WebSocket + MQTT subscriber
├── templates/                 # Mission Control UI templates
└── static/                    # Mission Control UI assets

```

## Running the PoC

### 1. Install dependencies
```bash
cd poc
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Run tests (TDD verification)
```bash
pytest tests/unit -v
# Expected: 56 passed (as of February 1, 2026)
```

### 3. Run demo (without MQTT)
```bash
python demo.py --broker memory
# Uses InMemoryBroker - no Docker needed!
```

### 4. Run demo (with MQTT)
```bash
# Terminal 1: Start MQTT broker (from repo root)
cd ..
cd ops
docker compose up -d

# Terminal 2: Run demo
cd ..
cd poc
python demo.py --broker mqtt
```

## Mission Planner (Inventory + Role Assignment)

If you start the ops stack with inventory enabled, you can open:

- `http://localhost:5000/planner` (role assignment UI)

## Expected Output

```
[PoC Demo] Initializing fault injection system...
[PoC Demo] Broker: InMemoryBroker
[PoC Demo] Registered fault: RF_LOSS_BURST

[PoC Demo] Simulating 40 telemetry messages...

[00] D001 @ t=0.0s   -> PASSED (battery: 100.0%)
[01] D001 @ t=1.0s   -> PASSED (battery: 99.8%)
[02] D001 @ t=2.0s   -> PASSED (battery: 99.6%)
[03] D001 @ t=3.0s   -> DROPPED (RF_LOSS_BURST active)
[04] D001 @ t=4.0s   -> DROPPED (RF_LOSS_BURST active)
[05] D001 @ t=5.0s   -> DROPPED (RF_LOSS_BURST active)
[06] D001 @ t=6.0s   -> PASSED (burst ended)
...

[PoC Demo] Summary:
  Total messages: 40
  Passed: ...
  Dropped: ...
  Fault activations: ...

[PoC Demo] OK: Fault injection working
[PoC Demo] OK: Hexagonal architecture validated
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

# Need MQTT? Swap in one line (then connect)
broker = MQTTBrokerAdapter(broker_host="localhost", broker_port=1883, client_id="poc-demo")
broker.connect()

# Domain code unchanged: publish the same payloads to the same topics
broker.publish("fleet/D001/telemetry", {"drone_id": "D001", "battery_pct": 97.2})
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

1. Validated architecture works
2. Add integration tests around MQTT publish/subscribe (optional)
3. Extend telemetry schema to include richer health/events
4. Feed telemetry into `mission_control.py` and validate end-to-end behavior

## Time Breakdown

- Setup + first test: 15 min
- Telemetry entity (TDD): 20 min
- FaultModel interface: 10 min
- RFLossBurstFault (TDD): 30 min
- Registry (TDD): 20 min
- MessageBroker port + adapters: 25 min
- Demo script: 20 min
- **Total: ~2 hours**
