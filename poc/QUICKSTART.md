# Quick Start: Run the PoC

**Last reviewed:** February 1, 2026

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
===================== 56 passed in 2.0s =====================
```

Note: Run `pytest poc/tests/unit -q` from repo root to confirm the current count on your machine.

## 3. Run Demo

### Option A: Watch all 5 fault models in action (recommended)

```powershell
python demo.py --faults all --messages 40
```

To publish the same stream to a real MQTT broker, add `--broker mqtt` (requires `ops/docker-compose.yml` running).

**Watch for:**
- **RF_LOSS_BURST**: Messages dropped (DROPPED)
- **GNSS_MULTIPATH**: Position offsets (lat/lon changes)
- **EKF_UNHEALTHY**: Position noise (altitude/position jitter)
- **THRUST_SHORTFALL**: Altitude loss (alt_m decreases)
- **BATTERY_SAG**: Battery drain (battery_pct drops faster)

### Option B: Watch specific faults

```powershell
# Just GPS issues
python demo.py --faults gnss --messages 30

# Just battery problems
python demo.py --faults battery --messages 30

# Just RF dropouts
python demo.py --faults rf --messages 20
```

### Option C: Original simple demo

```powershell
python demo.py --broker memory --messages 20
```

**Expected output:**
```
[PoC Demo] Registered: RF_LOSS_BURST (every 10s, down 3s)
[PoC Demo] Registered: GNSS_MULTIPATH (every 15s, lasts 4s, ±8m offset)
[PoC Demo] Registered: EKF_UNHEALTHY (every 20s, lasts 5s, σ=12m noise)
[PoC Demo] Registered: THRUST_SHORTFALL (every 25s, lasts 6s, -1.5m/s altitude)
[PoC Demo] Registered: BATTERY_SAG (every 30s, lasts 8s, -1.2%/s drain)

[PoC Demo] Simulating 40 telemetry messages (0.5s intervals)...

[00] D001 @ t=0.0s  -> PASSED                                               (bat: 100.0%)
[01] D001 @ t=0.5s  -> PASSED                                               (bat: 99.9%)
...
[12] D001 @ t=6.0s  -> DROPPED    [RF_LOSS_BURST]                            (battery: 98.8%)
...
[20] D001 @ t=10.0s -> PASSED      [GNSS_MULTIPATH]                          (bat: 98.0%, alt: 100.0m)
[21] D001 @ t=10.5s -> PASSED      [GNSS_MULTIPATH]                          (bat: 97.9%, alt: 100.0m)
...

[PoC Demo] ========== SUMMARY ==========
  Total messages: 40
  Passed: 32 (80%)
  Dropped: 8 (20%)

  Fault Activations:
    BATTERY_SAG: 12 times
    EKF_UNHEALTHY: 8 times
    GNSS_MULTIPATH: 10 times
    RF_LOSS_BURST: 8 times
    THRUST_SHORTFALL: 9 times

[PoC Demo] OK: All 5 fault model(s) demonstrated
```

## What This Proves

OK: **All 5 fault models working** (RF_LOSS_BURST, GNSS_MULTIPATH, EKF_UNHEALTHY, THRUST_SHORTFALL, BATTERY_SAG)  
OK: **Domain logic has zero external dependencies**  
OK: **Tests run in <2 seconds (56 tests, no MQTT broker needed)**  
OK: **Easy to swap InMemory <-> MQTT brokers**  
OK: **Fault models are pluggable via registry**  

## Observing Missions Live

The demo shows **simulated telemetry** with faults injected in real-time. Watch for:

| Fault | Observable Effect | Demo Flag |
|-------|-------------------|-----------|
| **RF_LOSS_BURST** | Message drops (DROPPED) | `--faults rf` |
| **GNSS_MULTIPATH** | Position offsets (lat/lon changes) | `--faults gnss` |
| **EKF_UNHEALTHY** | Position noise (random jitter) | `--faults ekf` |
| **THRUST_SHORTFALL** | Altitude loss (alt_m decreases) | `--faults thrust` |
| **BATTERY_SAG** | Battery drain (battery_pct drops) | `--faults battery` |

Run `python demo.py --help` to see all options.  

## Next Steps

See [poc/README.md](README.md) for architecture details. For broader project notes/runbooks, see `.context/project/docs/13_demo_runbook.md` and `.context/project/docs/14_mqttcool_steps.md`.
