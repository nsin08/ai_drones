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

**Expected Console Output:**
```
======================================================================
🚁 DRONE FLEET MISSION SIMULATOR
======================================================================
MQTT Broker: localhost:1883
Grafana Dashboard: http://localhost:3000
Mission Duration: 60s per mission
======================================================================

🎯 Mission 1: PATROL
Objective: Follow route with multi-drone coverage
Formation: LEADER + POINT_MAN + 2x WINGMAN + SCOUT

  📍 Waypoint 1 reached
  📍 Waypoint 2 reached
  ⚠️  Fault injected on PATROL-03: battery dropped to 84.2%
  📍 Waypoint 3 reached
  ⚠️  Fault injected on PATROL-05: battery dropped to 76.5%

✅ Mission completed: 60s elapsed

🎯 Mission 2: ESCORT
Objective: Protect moving asset with safety envelope
Formation: LEADER (on asset) + WINGMAN wedge + POINT_MAN + RELAY

  ⚠️  Fault injected on ESCORT-01: battery dropped to 89.3%
  ⚠️  Fault injected on ESCORT-04: battery dropped to 92.1%

✅ Mission completed: 60s elapsed

🎯 Mission 3: PERIMETER_GUARD
Objective: Maintain watch over fixed perimeter
Formation: LEADER (coordinator) + sector guards + roving POINT_MAN

  ⚠️  Fault injected on GUARD-02: battery dropped to 81.7%

✅ Mission completed: 60s elapsed
```

**Option B: Single mission (longer observation)**
```powershell
# PATROL: Follow waypoint route with 5-drone formation
python mission_simulator.py --mission patrol --duration 120

# ESCORT: Protect moving asset with safety envelope
python mission_simulator.py --mission escort --duration 120

# PERIMETER_GUARD: Watch fixed perimeter with sector coverage
python mission_simulator.py --mission perimeter --duration 120
```

**Option C: Custom broker/port**
```powershell
# If MQTT on different host
python mission_simulator.py --mission all --broker 192.168.1.100 --port 1883 --duration 90
```

### What Each Mission Does

#### PATROL Mission
```
5 drones follow Delhi route with coverage formation:

PATROL-01 (LEADER)         → Follows waypoints: Delhi → N → E → S → W → loop
PATROL-02 (POINT_MAN)      → Runs 60m ahead (forward scout)
PATROL-03 (WINGMAN LEFT)   → 40m left flank
PATROL-04 (WINGMAN RIGHT)  → 40m right flank  
PATROL-05 (SCOUT)          → Circles perimeter (30m radius, 360°)

Timeline:
- 0s:   Formation initializes at Delhi (28.6139°N, 77.2090°E)
- 15s:  Waypoint 1 reached (north)
- 30s:  Waypoint 2 reached (east)
- 45s:  Waypoint 3 reached (south)
- 60s:  Return to start (west)
- Plus: Random faults every 20s (30% chance)
```

#### ESCORT Mission
```
5 drones protect moving asset with defensive formation:

ESCORT-01 (LEADER)         → Tracks moving asset (0.5m/s northeast)
ESCORT-02 (WINGMAN LEFT)   → Left flank (30m offset)
ESCORT-03 (WINGMAN RIGHT)  → Right flank (30m offset)
ESCORT-04 (POINT_MAN)      → Probes 100m ahead on route
ESCORT-05 (RELAY)          → Maintains comms anchor (50m behind)

Asset Movement:
- Simulates vehicle moving NE at 0.5m/s
- Formation maintains protective envelope
- All drones adjust to track asset

Timeline:
- 0s:   Asset at start, formation established
- 30s:  Asset moved ~15m north, formation adjusted
- 60s:  Asset moved ~30m NE, all drones repositioned
- Plus: Random faults every 20s (30% chance)
```

#### PERIMETER_GUARD Mission
```
5 drones maintain watch over fixed 500m perimeter:

GUARD-01 (LEADER)          → Center coordinate (28.6139°N, 77.2090°E) [loiter]
GUARD-02 (WINGMAN SECTOR1) → NE sector (loiter, slow rotation)
GUARD-03 (WINGMAN SECTOR2) → E sector (loiter, slow rotation)
GUARD-04 (SCOUT SECTOR3)   → SW sector (loiter, slow rotation)
GUARD-05 (POINT_MAN)       → Roving boundary perimeter (continuous patrol)

Sector Coverage:
- 3 guards occupy 120° spacing around perimeter
- Rotate slowly for continuous coverage
- POINT_MAN roves full boundary for detailed inspection
- LEADER at center for oversight/coordination

Timeline:
- 0s:   All drones in position (LOITER mode)
- 20s:  Sectors rotated ~10° (continuous coverage)
- 40s:  Sectors rotated ~20°
- 60s:  Sectors back to ~0° (full rotation cycle)
- Plus: Random faults every 20s (30% chance)
```

### 4. Open Grafana Dashboard

1. Open browser: **http://localhost:3000**
2. Login: `admin` / `admin` (skip password change for demo)
3. Navigate: **Dashboards → Drone Fleet Mission Dashboard**

You should see **live telemetry** updating every second! 🎉

## What to Expect in Grafana Dashboard

Wait ~5-10 seconds after starting mission for data to appear. Then watch these panels update live:

### Panel 1: Battery Levels Time-Series (Top Left)
```
Shows battery % over time for all 5 drones

PATROL Mission Example (0-60s):
┌─────────────────────────────────────┐
│ 100%│    PATROL-01 ╱╲              │
│     │             ╱  ╲╱╲           │ PATROL-01 (LEADER)
│  90%│ PATROL-02  ╱      ╲╱╲        │ PATROL-02 (POINT_MAN)
│     │           ╱          ╲      │ PATROL-03 (WINGMAN)
│  80%│ PATROL-03 ╱   ⚠️ FAULT      │ PATROL-04 (WINGMAN)
│     │         ╱     (drops 15%)   │ PATROL-05 (SCOUT)
│  70%│ PATROL-04,05                │
│     │ (smooth decline)             │
└─────────────────────────────────────┘
     0s          30s         60s

What to watch:
- All drones drain ~0.1% per second (natural)
- Random drops of 5-15% (fault injection) 
- Identify fault patterns
- LEADER typically higher (less movement)
```

### Panel 2: Current Battery Gauges (Top Right)
```
Live battery status with color coding

PATROL Mission (at 30s):
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│ 97%  │  │ 94%  │  │ 79%  │  │ 96%  │  │ 91%  │
│  🟢  │  │  🟢  │  │  🟡  │  │  🟢  │  │  🟢  │
│P-01  │  │P-02  │  │P-03* │  │P-04  │  │P-05  │
└──────┘  └──────┘  └──────┘  └──────┘  └──────┘

* = Recently faulted (battery dropped)

Color Legend:
🔴 Red   (<20%):  Critical - land immediately
🟡 Yellow (20-50%): Warning - prepare for landing
🟢 Green (>50%):   Healthy - continue mission

Timeline Progression:
- 0s:  All 🟢 (100%)
- 30s: Most 🟢, occasional 🟡 after faults
- 60s: All drained to ~95% (natural wear)
```

### Panel 3: Altitude by Drone (Bottom Left)
```
Altitude profiles showing formation height separation

PATROL Mission Example:
┌─────────────────────────────────────┐
│ 65m │                   PATROL-05  │
│     │                   (SCOUT)    │
│ 55m │                   ╱╲╱╲       │
│     │  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱            │
│ 50m │ PATROL-01,02,03,04            │
│     │ (formation)                    │
│ 45m │                                │
└─────────────────────────────────────┘
     0s          30s         60s

What to watch:
- PATROL-05 (SCOUT) higher (~60m) for perimeter visibility
- Other 4 drones maintain ~50m (formation cohesion)
- Steady altitude = good GPS + stable flight
- Altitude drops may indicate THRUST_SHORTFALL fault injection

ESCORT Mission: All drones at ~40m (tight envelope)
PERIMETER_GUARD: Mix of 50m (sectors) + 70m (LEADER center)
```

### Panel 4: Active Missions Pie Chart (Top Right, after 60s)
```
Distribution of active mission types during "all" run

At Different Times:
┌─────────┐  0-60s:   PATROL (100%)
│ PATROL  │  ✅ PATROL-01,02,03,04,05 active
│  100%   │
│  [████] │  60-120s: ESCORT (100%)
└─────────┘  ✅ ESCORT-01,02,03,04,05 active
             120-180s: PERIMETER_GUARD (100%)
             ✅ GUARD-01,02,03,04,05 active

Each mission runs sequentially, chart updates between transitions.
```

### Panel 5: Fleet Status Table (Center, Full Width)
```
Real-time snapshot of all drone states

Drone ID         Mission Type   Role        Lat      Lon      Alt   Battery  Mode  Status
─────────────────────────────────────────────────────────────────────────────────────────
PATROL-01        PATROL         LEADER      28.615  77.210   50.0   95.2%   AUTO  IN_PROGRESS
PATROL-02        PATROL         POINT_MAN   28.620  77.215   45.0   94.1%   AUTO  IN_PROGRESS
PATROL-03        PATROL         WINGMAN     28.610  77.205   50.0   79.3%   AUTO  IN_PROGRESS ⚠️ (faulted)
PATROL-04        PATROL         WINGMAN     28.610  77.215   50.0   96.1%   AUTO  IN_PROGRESS
PATROL-05        PATROL         SCOUT       28.613  77.208   60.5   91.2%   AUTO  IN_PROGRESS

Updates every 1 second! Watch coordinates change in real-time:
- PATROL-01 lat increases (moving north on route)
- PATROL-02 leads ahead
- PATROL-05 traces circle pattern (lon/lat orbit)
```

### Panel 6: Drones by Mission Role (Bottom Left)
```
Distribution of roles across fleet

PATROL Mission:
┌─────────────┐
│  LEADER 20% │  1 drone
│  POINT_MAN  │
│   WINGMAN   │  2 drones
│    SCOUT    │
│    RELAY  0%│  0 drones
└─────────────┘

ESCORT Mission:
┌─────────────┐
│  LEADER 20% │  
│  POINT_MAN  │  1 each
│   WINGMAN   │  2 drones
│    SCOUT 0% │
│    RELAY 20%│  1 drone (comms anchor)
└─────────────┘

PERIMETER_GUARD Mission:
┌─────────────┐
│  LEADER 20% │
│  POINT_MAN  │  1 drone (roving)
│   WINGMAN   │  2 drones (sectors)
│    SCOUT 20%│
│    RELAY  0%│
└─────────────┘
```

### Panel 7: Active Faults Count (Bottom Right)
```
Real-time fault event counter

PATROL Mission (with fault injection):
┌──────────────────────┐
│   Active Faults: 0   │  0s:   no faults
│   Events: ●●●        │  20s:  ⚠️  PATROL-03 fault (-15% battery)
│                      │  35s:  no active faults (already counted)
└──────────────────────┘  40s:  ⚠️  PATROL-05 fault (-8% battery)
                         55s:  no active faults

Counter resets when faults expire. Spikes show when new faults injected.
Each fault = 5-15% battery drop for ~10 seconds.

Total faults injected per mission: ~2-3 (30% chance every 20s)
```

### Observable Mission Behaviors

**🎯 PATROL Mission (60 seconds):**
- 📍 Watch LEADER move through waypoints (latitude increases from 28.614→28.620)
- 🎯 POINT_MAN runs 60m ahead on route (higher latitude/longitude)
- 🛡️ WINGMAN drones flank left/right (symmetric about route)
- 🔍 SCOUT sweeps perimeter in circular pattern (coordinates orbit)
- 📊 Altitude: SCOUT highest (~60m) for visibility, others ~50m
- ⚠️ Expect 2-3 fault events with battery drops 5-15%
- ✅ All drones complete 4-point route and return to start

**🚗 ESCORT Mission (60 seconds):**
- 🚗 LEADER tracks moving asset continuously northeast (lat/lon increase steadily)
- ⚔️ WINGMAN maintain fixed offsets (left/right flanks, 30m separation)
- 🕵️ POINT_MAN probes 100m ahead on trajectory (forward scout)
- 📡 RELAY stays 50m behind (comms anchor, loiter mode)
- 📊 Consistent altitude ~40m (tight protective envelope)
- ⚠️ Expect 2-3 fault events (battery drops 5-15%)
- ✅ Asset reaches destination with formation fully intact

**🔒 PERIMETER_GUARD Mission (60 seconds):**
- 🎯 LEADER stays at center coordinate (28.6139°N, 77.2090°E, loiter, 70m)
- 🔒 3x Guards (WINGMAN/SCOUT) occupy rotating sectors (120° spacing)
- 🔄 Watch sectors rotate slowly (~10° per 20 seconds, continuous coverage)
- 🚶 POINT_MAN roves full boundary perimeter continuously
- 📊 Altitude: LEADER high (70m oversight), guards ~50m, POINT_MAN ~55m
- ⚠️ Expect 2-3 fault events (battery drops 5-15%)
- ✅ Complete 360° coverage maintained throughout, no blind spots

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

## Command Cheat Sheet

### Quick Start (Copy-Paste)

```powershell
# Terminal 1: Start infrastructure
cd d:\wsl_shared\projects\ai_drones\ops
docker compose up -d
```

```powershell
# Terminal 2: Run mission
cd d:\wsl_shared\projects\ai_drones\poc
pip install paho-mqtt
python mission_simulator.py --mission all --duration 60
```

```powershell
# Browser: Open dashboard
http://localhost:3000
# Login: admin / admin
# Navigate: Dashboards → Drone Fleet Mission Dashboard
```

### Common Command Patterns

| Goal | Command |
|------|---------|
| **Watch all missions back-to-back** | `python mission_simulator.py --mission all --duration 60` |
| **Deep dive into PATROL** | `python mission_simulator.py --mission patrol --duration 120` |
| **Deep dive into ESCORT** | `python mission_simulator.py --mission escort --duration 120` |
| **Deep dive into PERIMETER** | `python mission_simulator.py --mission perimeter --duration 120` |
| **Debug: Monitor MQTT messages** | `docker exec -it mosquitto-broker mosquitto_sub -t "fleet/#" -v` |
| **Debug: Check InfluxDB data** | `docker exec -it influxdb influx query 'from(bucket:"telemetry") \|> range(start:-5m) \|> limit(n:20)'` |
| **Restart everything** | `docker compose down && docker compose up -d` |
| **Cleanup (full reset)** | `docker compose down -v` |

### Dashboard Tabs (What to Click)

1. **Grafana Home** → **Dashboards** → **Drone Fleet Mission Dashboard**
2. OR bookmark: `http://localhost:3000/d/drone-fleet-missions`

### Monitoring Checklist

After starting mission simulator, watch Grafana for:

- ✅ **Battery panel**: All 5 drones appear, battery declining
- ✅ **Altitude panel**: SCOUT higher, others in formation
- ✅ **Fleet table**: All 5 drones listed with coordinates
- ✅ **Fault counter**: Shows 0, spikes to 1-2 during mission (if fault injected)
- ✅ **Role distribution**: Pie chart shows LEADER/WINGMAN/POINT_MAN/SCOUT/RELAY
- ⚠️ **No data?** Wait 10s, check MQTT bridge (see Troubleshooting)

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
