# Drone Fleet Mission Visualization with Grafana

Demonstrates **Mission v1** scenarios (PATROL, ESCORT, PERIMETER_GUARD) with real-time Grafana dashboard visualization.

## Architecture

```
┌─────────────────┐     MQTT      ┌──────────────┐
│ Mission         ├──────────────►│  Mosquitto   │
│ Simulator       │  Telemetry    │  Broker      │
│ (Python)        │               │  :1883       │
└─────────────────┘               └──────┬───────┘
                                         │
                                         │ Subscribe
                                         ▼
                                  ┌──────────────┐
                                  │  Telegraf    │
                                  │  (MQTT→DB)   │
                                  └──────┬───────┘
                                         │
                                         │ Write
                                         ▼
                                  ┌──────────────┐
                                  │  InfluxDB    │
                                  │  Time Series │
                                  │  :8086       │
                                  └──────┬───────┘
                                         │
                                         │ Query
                                         ▼
                                  ┌──────────────┐
                                  │   Grafana    │
                                  │  Dashboard   │
                                  │  :3000       │
                                  └──────────────┘
```

## Quick Start

### 1. Start Infrastructure (3 minutes)

```powershell
cd ops
docker compose up -d
```

**Services starting:**
- ✅ Mosquitto MQTT broker (port 1883)
- ✅ InfluxDB time-series database (port 8086)
- ✅ Telegraf metrics collector
- ✅ Grafana dashboard (port 3000)

**Check status:**
```powershell
docker compose ps
```

All services should show "healthy" status.

### 2. Install Python Dependencies

```powershell
cd ../poc
pip install paho-mqtt
```

### 3. Run Mission Simulator

**Option A: All 3 missions (recommended first run)**
```powershell
python mission_simulator.py --mission all --duration 60
```

**Option B: Single mission**
```powershell
# PATROL: Follow waypoint route with 5-drone formation
python mission_simulator.py --mission patrol --duration 90

# ESCORT: Protect moving asset with safety envelope
python mission_simulator.py --mission escort --duration 90

# PERIMETER_GUARD: Watch fixed perimeter with sector coverage
python mission_simulator.py --mission perimeter --duration 90
```

### 4. Open Grafana Dashboard

1. Open browser: **http://localhost:3000**
2. Login: `admin` / `admin` (skip password change for demo)
3. Navigate: **Dashboards → Drone Fleet Mission Dashboard**

You should see **live telemetry** updating every second! 🎉

## Dashboard Features

### Real-Time Panels

| Panel | What It Shows | Mission Insight |
|-------|---------------|-----------------|
| **Battery Levels** | Time-series per drone | Watch battery drain, spot anomalies |
| **Current Battery Gauges** | Live battery status | Red (<20%), Yellow (20-50%), Green (>50%) |
| **Altitude by Drone** | Altitude profiles | See formation altitude separation |
| **Active Missions by Type** | Mission distribution | PATROL vs ESCORT vs PERIMETER_GUARD count |
| **Fleet Status Table** | Full drone state | drone_id, role, position, battery, mode |
| **Drones by Mission Role** | Role distribution | LEADER, WINGMAN, POINT_MAN, SCOUT, RELAY |
| **Active Faults Count** | Fault events | Injected faults during mission |

### Observable Mission Behaviors

**PATROL Mission:**
- 📍 Watch LEADER move through waypoints
- 🎯 POINT_MAN runs ahead (higher latitude)
- 🛡️ WINGMAN drones flank left/right
- 🔍 SCOUT sweeps perimeter in circular pattern
- 📊 Altitude: SCOUT highest for visibility

**ESCORT Mission:**
- 🚗 LEADER tracks moving asset
- ⚔️ WINGMAN in wedge formation (forward flanks)
- 🕵️ POINT_MAN probes ahead on route
- 📡 RELAY maintains comms anchor (behind formation)
- 📊 Consistent altitude for escort envelope

**PERIMETER_GUARD Mission:**
- 🎯 LEADER coordinates from center (loiter mode)
- 🔒 WINGMAN/SCOUT occupy 3 sectors (120° spacing)
- 🔄 Sectors rotate slowly for continuous coverage
- 🚶 POINT_MAN roves boundary perimeter
- 📊 Altitude: LEADER highest for oversight

## Mission Simulator Details

### Command Line Options

```powershell
python mission_simulator.py --help

Options:
  --mission {patrol,escort,perimeter,all}  # Mission type
  --duration SECONDS                        # Duration per mission (default: 60)
  --broker HOSTNAME                         # MQTT broker (default: localhost)
  --port PORT                              # MQTT port (default: 1883)
```

### Telemetry Published

Each drone publishes to: `fleet/{drone_id}/telemetry`

**Message format:**
```json
{
  "drone_id": "PATROL-01",
  "mission_type": "PATROL",
  "mission_role": "LEADER",
  "lat": 28.6139,
  "lon": 77.2090,
  "altitude_m": 50.0,
  "battery_pct": 95.3,
  "velocity_mps": 5.0,
  "mode": "AUTO",
  "mission_status": "IN_PROGRESS",
  "fault_count": 0,
  "timestamp": 1738368000.123
}
```

### Fault Injection

The simulator randomly injects faults:
- 📉 Battery drops (5-15%)
- ⚠️ Fault counter increments
- 🕒 Occurs every ~20 seconds (30% probability)

Watch the **Active Faults Count** panel spike!

## Troubleshooting

### Services not healthy

```powershell
cd ops
docker compose logs -f
```

Look for errors in Telegraf/InfluxDB connection.

### No data in Grafana

1. Check simulator is running: `python mission_simulator.py`
2. Verify MQTT messages: 
   ```powershell
   docker exec -it mosquitto-broker mosquitto_sub -t "fleet/#" -v
   ```
3. Check InfluxDB has data:
   ```powershell
   docker exec -it influxdb influx query 'from(bucket:"telemetry") |> range(start:-1m) |> limit(n:5)'
   ```

### Grafana shows "No data"

- Wait 10 seconds for first telemetry batch
- Check data source: **Configuration → Data Sources → InfluxDB-Telemetry**
- Verify token: `my-super-secret-auth-token`

## Cleanup

```powershell
# Stop simulator: Ctrl+C

# Stop infrastructure
cd ops
docker compose down

# Remove volumes (full reset)
docker compose down -v
```

## Architecture Benefits

✅ **Decoupled:** Simulator → MQTT → Database → Dashboard  
✅ **Scalable:** Add more drones, just publish to MQTT  
✅ **Real-time:** 1-second refresh, live mission visualization  
✅ **Persistent:** InfluxDB stores time-series for analysis  
✅ **Observable:** See mission patterns, formations, faults instantly  

## Next Steps

- Add map visualization (lat/lon plotting)
- Integrate with actual ArduPilot SITL
- Add mission planner UI (modify waypoints live)
- Connect AI advisor (fault prediction based on telemetry patterns)

---

**Demo Ready:** Start `mission_simulator.py` and open http://localhost:3000 to see missions in action! 🚁📊
