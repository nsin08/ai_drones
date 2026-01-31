# Quick Start: Run the PoC

## 1. Setup (2 minutes)

```powershell
cd poc
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run Tests (TDD Verification)

```powershell
pytest tests/unit -v
```

**Expected output:**
```
tests/unit/test_fault_registry.py::TestFaultModelRegistry::test_register_fault_model PASSED
tests/unit/test_fault_registry.py::TestFaultModelRegistry::test_create_fault_instance PASSED
tests/unit/test_rf_loss_burst.py::TestRFLossBurstFault::test_passes_message_initially PASSED
tests/unit/test_rf_loss_burst.py::TestRFLossBurstFault::test_drops_message_during_burst PASSED
tests/unit/test_telemetry.py::TestPosition::test_create_valid_position PASSED
tests/unit/test_telemetry.py::TestTelemetry::test_create_valid_telemetry PASSED
...
===================== 20 passed in 0.5s =====================
```

## 3. Run Demo

```powershell
python demo.py --broker memory --messages 20
```

**Expected output:**
```
[PoC Demo] Initializing fault injection system...
[PoC Demo] Broker: InMemoryBroker
[PoC Demo] Registered fault: RF_LOSS_BURST

[PoC Demo] Simulating 20 telemetry messages...
[PoC Demo] RF Burst: Every 5s, lasts 3s

[00] D001 @ t=0.0s   → ✅ PASSED (battery: 100.0%)
[01] D001 @ t=0.5s   → ✅ PASSED (battery: 99.8%)
...
[05] D001 @ t=2.5s   → ❌ DROPPED (RF_LOSS_BURST) (battery: 99.0%)
...

[PoC Demo] Summary:
  Total messages: 20
  Passed: 14 (70%)
  Dropped: 6 (30%)

[PoC Demo] ✅ Fault injection working!
[PoC Demo] ✅ Hexagonal architecture validated!
```

## What This Proves

✅ **Domain logic has ZERO external dependencies**  
✅ **Tests run in <1 second (no MQTT broker needed)**  
✅ **Easy to swap InMemory ↔ MQTT brokers**  
✅ **Fault models are pluggable via registry**  

## Next Steps

See [poc/README.md](README.md) for architecture details and [.context/project/IMPLEMENTATION-PLAN-TDD.md](../.context/project/IMPLEMENTATION-PLAN-TDD.md) for full implementation plan.
