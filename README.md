# Drone Fleet Ops MVP (MQTT + Mission Control V3 + SwarmSim)

**Last reviewed:** February 8, 2026

This repo contains a **production-ready V3 Mission Control system** for drone fleet operations:

- **Mission Control V3** — Flask backend + React + Vite SPA with real-time telemetry, command/ACK tracking, mission state machine
- **SwarmSim** — Virtual drone fleet simulator (10-17 drones) with formation offsets, battery drain, simulated latency
- **MQTT-based architecture** — Publish/subscribe for telemetry, commands, and ACKs
- **Hybrid fleet support** — Seamless integration with ArduPilot SITL (Phase 2) or real hardware (Edge Agent, Phase 2)

## Quick Start (Minimal Script-Based, Recommended for Development)

**Prerequisites:** Docker (for MQTT broker), Python 3.11+

### Terminal 1: Start MQTT Broker (Docker)
```powershell
cd ops
docker compose up mosquitto -d
# Broker runs on localhost:1883
```

### Terminal 2: Start Mission Control V3 (Backend + UI)
```powershell
cd poc
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python mission_control_v3.py
# API: http://localhost:5000/api
# SPA: http://localhost:5000
```

### Terminal 3: Start SwarmSim (Virtual Fleet)
```powershell
cd swarmsim
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python swarmsim.py --drones 12 --broker localhost --port 1883
# 12 virtual drones (SIM-001 to SIM-012) at 1 Hz telemetry
```

### Open Browser
```
http://localhost:5000/
```

**Expected:**
- ✓ Dark theme UI loads (React + Leaflet map)
- ✓ 12 drones appear in FleetRoster with roles (LEADER, WINGMAN, SCOUT, etc.)
- ✓ Map shows drone markers + home base (star icon)
- ✓ Real-time altitude/battery charts
- ✓ Command queue (empty until mission starts)

---

## Full Demo Scenario (15-20 minutes)

See [.context/project/docs/24_v3_demo_runbook.md](.context/project/docs/24_v3_demo_runbook.md) for:
- **Phase 1:** System startup & fleet discovery
- **Phase 2:** PERIMETER mission planning & execution
- **Phase 3:** Formation break & leader reassignment
- **Phase 4:** Bulk commands & mission abort
- **Troubleshooting checklist**

---

## Full Docker Setup (With Observability + SITL)

**Includes:** InfluxDB, Grafana dashboards, ArduPilot SITL containers, inventory service

### Start All Services
```powershell
cd ops
docker compose up -d
docker compose up -d --scale drone=3
# Services: Mosquitto, InfluxDB, Grafana, Mission Control V3, SwarmSim, Inventory, 3 SITL Drones
```

### Access Points
| Service | URL |
|---------|-----|
| **Mission Control V3** | http://localhost:5000 |
| **Inventory (Drone Roster)** | http://localhost:8001/inventory |
| **Grafana (Dashboards)** | http://localhost:3000 (admin/admin) |
| **MQTT Broker** | localhost:1883 |
| **InfluxDB API** | http://localhost:8086 |

### Hybrid Fleet (SwarmSim + SITL)
- **SwarmSim drones:** SIM-001 to SIM-012 (virtual, always on)
- **SITL drones:** SITL-001 to SITL-003 (ArduPilot containers)
- **Total:** 15 drones visible in Fleet Roster

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (React + Vite SPA)           │
│  - Dark theme UI with real-time telemetry visualization │
│  - Mission planner (PATROL, PERIMETER, ESCORT)          │
│  - Command queue with ACK/timeout tracking              │
│  - Event timeline + charts                              │
└────────────────┬────────────────────────────────────────┘
                 │ WebSocket (Socket.IO)
                 ↓
┌────────────────────────────────────────────────────────┐
│         Mission Control V3 (Flask + SocketIO)          │
│  - REST API: /api/mission/*, /api/command/*            │
│  - Mission FSM: IDLE→PLANNING→PLANNED→ACTIVE→PAUSED    │
│  - Command timeout tracking (10s)                       │
│  - Bulk command dispatch with cmd_group_id             │
│  - Formation break detection                            │
└────────┬──────────────────────────────┬────────────────┘
         │ MQTT Pub/Sub                 │ Telemetry fetch
         ↓                              ↓
┌────────────────────────────────────────────────────────┐
│                 MQTT Broker (Mosquitto)                │
│  Topics:                                               │
│  - fleet/{id}/telemetry (1 Hz per drone)              │
│  - fleet/{id}/command (command dispatch)              │
│  - fleet/system/command_ack (ACK from drones)         │
│  - fleet/system/event (formation alerts)              │
└────┬────────────────────────────────────┬─────────────┘
     │                                    │
     ↓ MQTT Subscribe                     ↓ MQTT Subscribe
┌──────────────────────┐          ┌─────────────────────┐
│  SwarmSim            │          │  Inventory Service  │
│  (Virtual Fleet)     │          │  (SITL Bridge)      │
│  - 10-17 drones      │          │  - MAVLink ↔ MQTT   │
│  - 1 Hz telemetry    │          │  - Auto-discovery   │
│  - Formation offsets │          │  - Health tracking  │
│  - Battery drain     │          │  - 3+ SITL drones   │
│  - ACK simulation    │          │                     │
└──────────────────────┘          └─────────────────────┘
```

### Drone ID Namespacing
- `SIM-###` — SwarmSim virtual drones
- `SITL-###` — ArduPilot SITL containers
- `HW-###` — Real hardware (Edge Agent, Phase 2)

---

## File Organization

```
ai_drones/
├── poc/
│   ├── mission_control_v3.py     (V3 backend: 890 lines)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── src/
│   │   ├── adapters/
│   │   ├── domain/
│   │   └── ports/
│   └── tests/
├── swarmsim/
│   ├── swarmsim.py               (Virtual fleet: 546 lines)
│   ├── requirements.txt
│   └── Dockerfile
├── ui/
│   ├── src/
│   │   ├── components/           (14 components)
│   │   ├── stores/               (Zustand state)
│   │   ├── App.jsx, main.jsx
│   │   └── App.css, theme.css
│   ├── dist/                     (Production build)
│   ├── package.json
│   └── vite.config.js
├── ops/
│   ├── docker-compose.yml        (7 services)
│   ├── mosquitto.conf
│   ├── telegraf.conf
│   └── grafana/
├── inventory/
│   ├── app.py                    (FastAPI)
│   └── Dockerfile
├── docs/
│   ├── presentations/            (Executive + technical)
│   └── V3_DEMO_QUICKSTART.md
└── .context/
    ├── project/docs/
    │   ├── 17_v3_implementation_plan.md
    │   ├── 18_v3_ui_spec.md
    │   ├── 19_v3_api_contract.md
    │   ├── 20_v3_mission_planning_protocol.md
    │   ├── 21_v3_command_state_machine.md
    │   ├── 22_v3_swarm_behavior.md
    │   └── 24_v3_demo_runbook.md
```

---

## Key Features (V3)

### Mission State Machine
```
IDLE --[assign_mission]--> PLANNING --[plan_mission]--> PLANNED --[start_mission]--> ACTIVE
                                                                                         ↓
                                                                        [pause] ← PAUSED ←┤
                                                                                         ↓
                                                        [abort] → ABORTED / [completed] ← COMPLETED
```

### Command Lifecycle
- `REQUESTED` — sent to drone
- `ACKED` — drone confirmed within timeout
- `TIMED_OUT` — no ACK after 10 seconds
- `COMPLETED_LATE` — ACK arrived after timeout (tracked)

### Formation Behavior
- **Offsets per role:** LEADER (0,0), WINGMAN (±30m), SCOUT (60m), etc.
- **Formation break:** Leader HOLD/RETURN/LAND → auto-pause mission
- **Leader reassignment:** UI allows reassign + resume

---

## Development Setup

### Build UI
```powershell
cd ui
npm install
npm run build
# Output: dist/index.html + assets
```

### Run Tests (PoC domain models)
```powershell
cd poc
python -m pytest tests/unit -q
```

### Code Quality
```powershell
cd ui
npm run lint
```

---

## Deployment

### Local Production (Docker)
```powershell
cd ops
docker compose -f docker-compose.yml up -d
# All services auto-start on reboot (restart: unless-stopped)
```

### Cloud / VM
- Push image to registry: `docker push my-registry/mission-control-v3`
- Deploy via Kubernetes or Docker Swarm
- Update MQTT broker address in env vars

---

## Hardware Path (Phase 2)

To integrate real drones:

1. **Edge Agent** (MAVLink serial/UDP → MQTT)
2. **TLS MQTT** configuration
3. **Inventory registry** (heartbeat-based discovery)

No UI changes required — just swap MQTT topic namespace from `SIM-` → `HW-`.

---

## Troubleshooting

### No drones appear in UI
```powershell
# 1. Check MQTT broker is running
docker exec mosquitto mosquitto_sub -h localhost -t "fleet/+/telemetry" -C 1

# 2. Check SwarmSim is connected
# (Look for "MQTT connected (rc=0)" in terminal)

# 3. Check Mission Control logs
# (WebSocket should show "telemetry_update" messages)
```

### Commands timeout
```powershell
# Check SwarmSim received command
# (Look for "[SIM-###] Processing command" in terminal)

# Check ACK published to MQTT
docker exec mosquitto mosquitto_sub -h localhost -t "fleet/system/command_ack" -C 1
```

### Build errors
```powershell
# Rebuild UI
cd ui
npm install
npm run build

# Verify dist/ exists with index.html
ls dist/index.html
```

---

## References

- **Demo runbook:** [24_v3_demo_runbook.md](.context/project/docs/24_v3_demo_runbook.md)
- **API contract:** [19_v3_api_contract.md](.context/project/docs/19_v3_api_contract.md)
- **Presentations:** [docs/presentations/00_INDEX.md](docs/presentations/00_INDEX.md)
- **Framework:** [GitHub: space_framework](https://github.com/nsin08/space_framework)

