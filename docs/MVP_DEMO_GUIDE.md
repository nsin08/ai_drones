# MVP Demo Guide: AI Drones Fleet Ops

**Duration:** ~15 minutes end-to-end  
**Prerequisites:** Docker Desktop, Python 3.11, pip  
**Demo Goal:** Show real-time drone telemetry with fault injection via MQTT

---

## Quick Start (5 minutes)

### Step 1: Start MQTT Broker (Docker)

```bash
cd ops
docker-compose up -d
```

Verify:
```bash
docker-compose ps
# Should show mosquitto-broker RUNNING
```

### Step 2: Install Python Dependencies

```bash
cd poc
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
pip install paho-mqtt  # For MQTT adapter
```

### Step 3: Run Integration Demo

```bash
cd ..
python integration/demo_mqtt.py
```

You should see:
```
[MQTT Demo] Drone Fleet Ops MVP - Integration Test
[Setup] Connecting to MQTT broker at localhost:1883...
[Setup] ✅ Connected to MQTT broker
[Setup] Initializing fault models...
[Setup] ✅ RF_LOSS_BURST fault registered

[Simulation] Starting 50 telemetry messages...
[000] t= 0.0s | Battery: 100.0% | ✅ PASSED
[001] t= 0.5s | Battery:  99.8% | ✅ PASSED
[002] t= 1.0s | Battery:  99.6% | ❌ DROPPED (RF_LOSS_BURST)
...
[Summary]
  Total messages: 50
  Passed:         20 (40%)
  Dropped:        30 (60%)
  Published:      20
```

---

## Debugging with MQTT.Cool (5 minutes)

### Download MQTT.Cool Test Client

Download from: https://www.emqx.com/en/try?product=MQTT.Cool

Or use online client: https://www.emqx.io/online-mqtt-client

### Connect to Broker

```
Host: localhost
Port: 1883
Protocol: MQTT
```

### Subscribe to Topics

Open 3 terminal tabs in MQTT.Cool:

**Tab 1: Watch Telemetry**
```
mqtt-cool-client-0$ sub ai_drones/telemetry/D001
Topic: ai_drones/telemetry/D001
Payload: {"drone_id":"D001","timestamp":1234567890.123,...}
```

**Tab 2: Watch Faults**
```
mqtt-cool-client-0$ sub ai_drones/faults/D001
Topic: ai_drones/faults/D001
Payload: {"fault_type":"RF_LOSS_BURST","active":true,...}
```

**Tab 3: Publish Commands (optional)**
```
mqtt-cool-client-0$ pub ai_drones/commands/D001/rtl
{"command":"RTL","reason":"Low battery"}
```

### Expected Behavior

While integration demo is running, you'll see in MQTT.Cool:

1. **Telemetry flowing in** (telemetry/D001)
   - Every 0.5s a new message arrives
   - Battery % decreases from 100 to ~75%
   - Position/velocity/mode fields constant

2. **Faults injected** (faults/D001)
   - Every 15s, RF_LOSS_BURST starts
   - Lasts 5 seconds (5 dropped messages)
   - Pattern repeats

3. **Command echo** (if you publish)
   - Your test commands appear in demo logs

---

## Full Architecture Flow

```
┌─────────────────────────────────────────┐
│ 1. MQTT Broker (Mosquitto)              │
│    docker-compose up -d                 │
│    listening on localhost:1883          │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│ 2. Fleet Simulator                      │
│    python integration/demo_mqtt.py      │
│                                         │
│    Publishes every 0.5s:                │
│    → ai_drones/telemetry/D001 {json}   │
│    → ai_drones/faults/D001 {json}      │
│                                         │
│    Subscribes to:                       │
│    → ai_drones/commands/D001/* {json}  │
└────────────┬────────────────────────────┘
             │
        ┌────┴────┐
        ↓         ↓
    ┌────────┐  ┌─────────────┐
    │ Unit   │  │ MQTT.Cool   │
    │ Tests  │  │ Test Client │
    │        │  │             │
    │✅ 22   │  │ Subscribe → │
    │passed  │  │ Watch flow  │
    │        │  │             │
    │        │  │ Publish →   │
    │        │  │ Send cmds   │
    └────────┘  └─────────────┘
```

---

## Next Steps: Full Integration

Once MVP demo runs, continue building:

### Phase 1.2: Additional Fault Models (3 SP)
- GNSS multipath errors
- EKF unhealthy detection  
- Thrust shortfall
- Battery sag

### Phase 1.3: Mission Planner Integration (5 SP)
- Real ArduPilot simulator (SITL)
- Mission Planner app receiving telemetry
- Send commands back via MQTT

### Phase 2: Full Fleet Operations (10+ SP)
- Multi-drone coordination
- Group mission planning
- AI advisory system
- Integration tests with real MQTT

---

## Troubleshooting

### "Connection refused" on localhost:1883

**Solution:** Start the broker
```bash
cd ops
docker-compose up -d
docker-compose logs mosquitto
```

### "No messages in MQTT.Cool"

**Solution:** Check topic name is correct
- Exact format: `ai_drones/telemetry/D001` (case-sensitive)
- Use wildcard: `ai_drones/#` to see all

### "paho-mqtt module not found"

**Solution:** Install it
```bash
pip install paho-mqtt==2.1.0
```

### Tests fail with import errors

**Solution:** Make sure you're in the poc directory
```bash
cd poc
pytest tests/unit -v
```

### Demo publishes but MQTT.Cool shows nothing

**Solution:** Restart MQTT.Cool connection:
1. Disconnect from broker
2. Reconnect with Host=localhost, Port=1883
3. Re-subscribe to topic

---

## Key Files

| File | Purpose |
|------|---------|
| `ops/docker-compose.yml` | Mosquitto broker config |
| `ops/mosquitto.conf` | MQTT settings |
| `poc/src/adapters/mqtt_broker.py` | Production MQTT adapter |
| `poc/src/domain/rf_loss_burst.py` | Fault model (TDD) |
| `integration/demo_mqtt.py` | Full integration demo |
| `docs/MQTT_SCHEMA.md` | Topic documentation |
| `poc/tests/unit/` | Unit tests (22 passing) |

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Messages/sec | 2 (0.5s interval) |
| Latency | <10ms (localhost MQTT) |
| Unit tests | 22/22 passing |
| Test runtime | ~0.03s |
| Fault detection | Deterministic per time window |

---

## Advancing to Real Hardware

Once MVP demo works:

### Mission Planner + ArduPilot (SITL)

1. Download ArduPilot + Mission Planner
2. Run SITL simulator (simulates real drone)
3. Point Fleet Services at SITL's MAVLink port
4. Bridge MAVLink ↔ MQTT via adapter

### Real Drone Integration

1. Flash ArduPilot to Pixhawk
2. Connect telemetry modem to GCS
3. Bridge GCS ↔ MQTT with MavProxy
4. Fleet Services controls via MQTT topics

---

## Questions?

Refer to:
- `docs/MQTT_SCHEMA.md` - All topic formats + examples
- `poc/README.md` - Architecture explanation
- Unit tests in `poc/tests/unit/` - Working code examples
