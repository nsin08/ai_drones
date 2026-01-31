# MQTT Topic Schema - AI Drones MVP

**MQTT Broker:** Eclipse Mosquitto (localhost:1883)

**Use MQTT.Cool Test Client to debug:** http://mqtt-cool.local/ or similar MQTT UI

---

## Topic Hierarchy

```
ai_drones/
├── telemetry/
│   └── {drone_id}/           # Drone sends raw telemetry
│       ├── position          # Lat/Lon/Alt
│       ├── battery           # Battery %
│       ├── mode              # Flight mode
│       └── armed             # Armed state
├── faults/
│   └── {drone_id}/           # Faults applied to this drone
│       ├── rf_loss           # RF signal loss
│       ├── gnss_error        # GPS errors
│       ├── ekf_unhealthy     # EKF failures
│       ├── thrust_short      # Thrust shortfall
│       └── battery_sag       # Battery sag
├── commands/
│   └── {drone_id}/           # Mission Planner sends commands
│       ├── mission           # Patrol/Escort/Perimeter
│       ├── rtl               # Return to launch
│       └── disarm            # Emergency shutdown
├── plans/
│   └── {group_id}/           # Group planner publishes plans
│       └── mission           # Current mission assignment
└── recommendations/
    └── {group_id}/           # AI advisory system
        └── suggested_action  # "Hold", "Return Home", "Land"
```

---

## Message Formats (JSON)

### Telemetry

**Topic:** `ai_drones/telemetry/{drone_id}/{field}`

```json
{
  "drone_id": "D001",
  "timestamp": 1769864000.123,
  "position": {
    "lat": 28.6139,
    "lon": 77.2090,
    "alt_m": 45.5
  },
  "battery_pct": 87.5,
  "velocity_mps": 12.3,
  "armed": true,
  "mode": "GUIDED"
}
```

### Faults

**Topic:** `ai_drones/faults/{drone_id}`

```json
{
  "fault_type": "RF_LOSS_BURST",
  "active": true,
  "since_timestamp": 1769864000.123,
  "parameters": {
    "every_sec": 180.0,
    "down_sec": 8.0
  }
}
```

#### Supported Fault Types

| Fault Type | Description | Effect | Default Parameters |
|------------|-------------|--------|-------------------|
| **RF_LOSS_BURST** | Radio frequency signal loss | Drops telemetry messages (returns None) | every_sec=180.0, down_sec=8.0 |
| **GNSS_MULTIPATH** | GPS multipath interference | Applies random lat/lon position offsets | every_sec=60.0, duration_sec=5.0, offset_range=10.0m |
| **EKF_UNHEALTHY** | Extended Kalman Filter failure | Injects Gaussian noise into position (lat/lon/alt) | every_sec=90.0, duration_sec=8.0, noise_stddev_m=15.0 |
| **THRUST_SHORTFALL** | Motor/propeller thrust loss | Reduces altitude cumulatively over time | every_sec=120.0, duration_sec=10.0, alt_loss_mps=2.0 |
| **BATTERY_SAG** | Battery voltage sag under load | Temporarily reduces battery percentage | every_sec=150.0, duration_sec=6.0, sag_pct=15.0 |

**Fault Behavior:**
- All faults follow a periodic pattern: activate every `every_sec`, remain active for `duration_sec`
- Per-drone state tracking: each drone experiences faults independently
- Telemetry modifications apply to current input (not cumulative across calls except THRUST_SHORTFALL)
- Faults can overlap (multiple faults active simultaneously)

### Commands

**Topic:** `ai_drones/commands/{drone_id}/{command_type}`

```json
{
  "command": "PATROL",
  "waypoints": [
    {"lat": 28.6139, "lon": 77.2090, "alt_m": 50},
    {"lat": 28.6150, "lon": 77.2100, "alt_m": 50}
  ],
  "speed_mps": 15.0
}
```

### Mission Plans

**Topic:** `ai_drones/plans/{group_id}/mission`

```json
{
  "group_id": "G001",
  "mission_type": "PATROL",
  "drone_assignments": {
    "D001": {"role": "primary", "waypoints": [...] },
    "D002": {"role": "secondary", "waypoints": [...] }
  },
  "created_at": 1769864000.123
}
```

### Recommendations

**Topic:** `ai_drones/recommendations/{group_id}/suggested_action`

```json
{
  "recommendation": "RETURN_HOME",
  "reason": "RF_LOSS_BURST detected on primary drone",
  "confidence": 0.95,
  "suggested_drones": ["D001"],
  "timestamp": 1769864000.123
}
```

---

## MQTT.Cool Debugging Setup

### 1. Subscribe to All Topics

In MQTT.Cool Test Client:

```
mqtt-cool-client-0$ sub ai_drones/# -d "Subscribe to all"
```

### 2. Monitor Specific Drone

```
mqtt-cool-client-0$ sub ai_drones/telemetry/D001 -d "Watch D001"
mqtt-cool-client-0$ sub ai_drones/faults/D001 -d "Watch faults"
```

### 3. Send Test Command

```
mqtt-cool-client-0$ pub ai_drones/commands/D001/mission '{"command":"PATROL","waypoints":[...]}'
```

### 4. Monitor Group Operations

```
mqtt-cool-client-0$ sub ai_drones/plans/G001/# -d "Watch group plan"
mqtt-cool-client-0$ sub ai_drones/recommendations/G001/# -d "Watch recommendations"
```

---

## Typical Message Flow

```
1. Simulator publishes telemetry
   ai_drones/telemetry/D001 → {...}

2. Fault injector modifies telemetry
   ai_drones/faults/D001 → {"fault_type": "RF_LOSS_BURST", ...}

3. Planner receives telemetry + faults
   ai_drones/plans/G001/mission → {...}

4. AI evaluates situation
   ai_drones/recommendations/G001/suggested_action → {...}

5. Mission Planner sends commands
   ai_drones/commands/D001/mission → {...}
```

---

## QoS & Retention

| Topic | QoS | Retain | Reason |
|-------|-----|--------|--------|
| telemetry/\* | 1 | No | High frequency, don't store |
| faults/\* | 1 | Yes | Important, UI needs current state |
| commands/\* | 1 | No | One-time actions |
| plans/\* | 1 | Yes | Group state, UI needs current |
| recommendations/\* | 1 | No | Advisory, not persistent |

---

## Testing with Python

```python
import paho.mqtt.client as mqtt
import json
import time

client = mqtt.Client("test-client")
client.connect("localhost", 1883, 60)

# Subscribe
client.subscribe("ai_drones/telemetry/#")
client.on_message = lambda c, u, m: print(f"{m.topic}: {m.payload}")

# Publish test telemetry
msg = {
    "drone_id": "D001",
    "timestamp": time.time(),
    "position": {"lat": 28.6139, "lon": 77.2090, "alt_m": 50},
    "battery_pct": 90.0
}
client.publish("ai_drones/telemetry/D001", json.dumps(msg))

client.loop_forever()
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| MQTT.Cool can't connect | Verify broker at localhost:1883, check firewall |
| No messages received | Check topic syntax (case-sensitive), verify subscription |
| Messages not persisted | Use `Retain` flag when publishing |
| High latency | Check network, consider QoS 0 for telemetry |
