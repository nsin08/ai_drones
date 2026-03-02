# V3 Implementation Plan (Mission Control + Real Drone Bridge)

**Last Updated:** February 8, 2026  
**Status:** Core V3 implementation complete. Ready for integration testing.  
**Goal:** Evolve the current MQTT/MAVLink PoC into a production-ready architecture that can swap SITL containers for real drones with minimal UI changes.

**Single source of truth:** This doc and `.context/project/docs/18_v3_ui_spec.md` are the canonical plan/spec for V3 execution. Keep them updated as work progresses.

**Target demo:** 5-20 drones on a single laptop (visual-first). Recommended demo source is hybrid SwarmSim (10-17 drones) + SITL (3-5 drones).

**Internet:** Allowed for demo (map tiles), but keep an airgapped option via configurable tile providers. Avoid runtime CDN dependencies in the SPA build.

---

## Key Deliverables (Feb 8)

### New Files Created

**Frontend (React + Vite SPA)**
- `ui/src/components/QuickActions.jsx` — Command dispatch buttons (HOLD/RETURN/DISABLE/ENABLE/ARM) + leader reassignment
- `ui/src/components/CommandQueue.jsx` — Live command list with status dots and late ACK badge
- `ui/src/components/BottomStrip.jsx` — Tabbed panel (AltitudeChart, BatteryChart, EventTimeline)
- `ui/src/components/ConfirmDialog.jsx` — Modal for destructive commands

**Backend (Flask + SocketIO)**
- `poc/mission_control_v3.py` — New V3 backend with mission FSM (IDLE→PLANNING→PLANNED→ACTIVE→PAUSED→ABORTED/COMPLETED), bulk commands, state snapshot, leader reassignment, command timeout tracking

**SwarmSim Service**
- `swarmsim/swarmsim.py` — Virtual drone fleet simulator (10-17 drones, SIM-### namespace, 1 Hz telemetry, formation offsets, battery drain, 100-300ms ACK latency)
- `swarmsim/Dockerfile`, `swarmsim/requirements.txt`

### Files Modified

**Frontend**
- `ui/src/index.css` — Replaced Vite defaults with V3 dark theme resets
- `ui/src/main.jsx` — Added theme.css and App.css imports
- `ui/src/App.css` — Aligned CSS class names to components (bottom-tabs, command-row, confirm-*, event-row)
- `ui/src/App.jsx` — Cleaned up boilerplate
- `ui/src/api.js` — Added pauseMission, resumeMission, abortMission, resetMission endpoints
- `ui/src/socket.js` — Fixed reconnection handler (inventory shape, snapshot nesting); added command_requested and event listeners
- `ui/src/components/TopBar.jsx` — Wired pause/resume/abort to actual backend API calls
- `ui/src/components/MissionSetup.jsx` — Aligned plan/start flow with V3 backend (assign→plan→start)

**Infrastructure**
- `ops/docker-compose.yml` — Added swarmsim service with healthcheck on mosquitto

**Build**
- `npx vite build` produces production bundle at `ui/dist/` (zero errors, 817 KB gzip)

---

## 0) Progress Tracker (V3)

Use this section as the status board. Check items off as they land.

- [x] M0: Protocol + schemas locked (API contract + planning + state machine + swarm behavior)  
  **✅ COMPLETE** — Docs 19-22 finalized; mission FSM, command FSM, bulk actions, formation behavior spec'd.

- [x] M1: React + Vite SPA skeleton (map renders, connects, dark theme)  
  **✅ COMPLETE** — Vite scaffold with Leaflet (dark filter), Socket.IO reconnect, Zustand stores, dark theme CSS.

- [x] M2: Fleet roster (inventory + telemetry-only drones) + selection  
  **✅ COMPLETE** — FleetRoster.jsx with multi-select, role dropdown, battery/mode display, OOF chip; fleetStore merges telemetry; stale detection (STALE_SEC=30s).

- [x] M3: Per-drone commands + command queue w/ ACK + timeouts  
  **✅ COMPLETE** — `POST /api/command/<verb>` endpoint; commandStore tracks REQUESTED→ACKED→TIMED_OUT lifecycle; CommandQueue.jsx shows status dots, late ACK badge; 10s ACK timeout thread.

- [x] M4: Bulk (swarm) commands with 1 confirm + `cmd_group_id`  
  **✅ COMPLETE** — `POST /api/command/bulk/<verb>` endpoint; QuickActions.jsx handles bulk dispatch; showConfirm modal displays affected drones; all commands share cmd_group_id.

- [x] M5: Mission planning tools (PATROL waypoints, PERIMETER geofence, ESCORT route)  
  **✅ COMPLETE** — CenterMap.jsx click handlers for PATROL/PERIMETER/ESCORT planning; MissionSetup.jsx mission type selector; assign→plan→start flow aligned with backend FSM.

- [x] M6: SwarmSim (10-17) + SITL (3-5) unified demo mode  
  **✅ COMPLETE** — SwarmSim service created (swarmsim/swarmsim.py); publishes telemetry at 1 Hz (0.5 Hz if >15), formation offsets per role, battery drain 0.5%/min, 100-300ms ACK latency, FORMATION_COMPROMISED event.

- [x] M7: Demo runbook + scripted scenario (repeatable)  
  **✅ COMPLETE** — Created `.context/project/docs/24_v3_demo_runbook.md` with 8-phase scripted scenario (15-20 min), troubleshooting guide, performance benchmarks, video recording checklist.

- [ ] M8 (later): Edge Agent + TLS MQTT + hardware path  
  **NOT STARTED** — Planned post-demo as Phase 2.

---

## 0.5) Implementation Summary (Feb 8, 2026)

### Frontend (React + Vite SPA)

| Component | Status | Details |
|-----------|--------|---------|
| **Stores (Zustand)** | ✅ Complete | fleetStore (telemetry + trail), missionStore (FSM state), commandStore (command lifecycle), selectionStore (multi-select), eventStore (timeline), uiStore (dialogs/filters) |
| **API client** | ✅ Complete | axios wrapper for `/api/inventory`, `/api/mission/*`, `/api/command/*`, `/api/state/snapshot`; pause/resume/abort/reset endpoints |
| **Socket.IO** | ✅ Complete | Reconnection strategy with state recovery; listeners for telemetry_update, command_ack, mission_changed, leader_election, command_requested, event |
| **TopBar** | ✅ Complete | Mission state badge, drone count, pause/resume/abort buttons wired to backend |
| **LeftPanel** | ✅ Complete | Container for MissionSetup + FleetRoster |
| **MissionSetup** | ✅ Complete | Type selector (PATROL/PERIMETER/ESCORT), assign→plan→start flow, reset button |
| **FleetRoster** | ✅ Complete | Multi-select list with role dropdown, battery/mode display, OOF chip, search filter |
| **CenterMap** | ✅ Complete | Leaflet map with drone markers (role-colored SVG), trails (100 points/drone), PATROL waypoint clicks, PERIMETER polygon, ESCORT route, click handlers |
| **RightPanel** | ✅ Complete | Container for QuickActions + CommandQueue |
| **QuickActions** | ✅ Complete | HOLD/RETURN/DISABLE/ENABLE/ARM buttons; bulk command dispatch; leader reassignment UI when PAUSED |
| **CommandQueue** | ✅ Complete | Command list sorted newest-first; status dots (REQUESTED/ACKED/FAILED/TIMED_OUT); late ACK badge; time-since display |
| **BottomStrip** | ✅ Complete | Tabbed panel: AltitudeChart (Recharts LineChart), BatteryChart (BarChart with color thresholds), EventTimeline (scrollable events) |
| **ConfirmDialog** | ✅ Complete | Modal for destructive commands; shows affected drone list; cancel/confirm actions |
| **Theme** | ✅ Complete | Dark theme CSS vars (theme.css) + component styles (App.css); Leaflet dark filter; no runtime CDN |
| **Build** | ✅ Complete | `vite build` produces `dist/index.html` + JS/CSS bundles (817 KB gzip); zero errors |

### Backend (Flask + SocketIO)

| Feature | Status | Details |
|---------|--------|---------|
| **Mission FSM** | ✅ Complete | IDLE → PLANNING → PLANNED → ACTIVE → PAUSED → COMPLETED/ABORTED; transition guards; state broadcast |
| **Mission endpoints** | ✅ Complete | `/api/mission/assign`, `/api/mission/plan`, `/api/mission/start`, `/api/mission/pause`, `/api/mission/resume`, `/api/mission/abort`, `/api/mission/reassign_leader`, `/api/mission/reset` |
| **Command FSM** | ✅ Complete | REQUESTED → SENT → ACKED/TIMED_OUT/FAILED; timeout tracking thread (2s interval); late ACK detection |
| **Command endpoints** | ✅ Complete | `/api/command/<hold\|return\|...\|set_role>` (single) + `/api/command/bulk/<verb>` (bulk) with cmd_group_id |
| **Formation break** | ✅ Complete | Leader HOLD/RETURN/LAND auto-pauses mission; per-drone exit from formation tracked |
| **State snapshot** | ✅ Complete | `/api/state/snapshot` returns full state (mission, drones, commands, events, leader_history) for Socket.IO reconnect recovery |
| **Event log** | ✅ Complete | Ring buffer (max 200 events); emitted via Socket.IO; includes INFO/WARN/CMD types |
| **Inventory proxy** | ✅ Complete | `/api/inventory` merges live drone_states with upstream inventory; stale detection (STALE_SEC=30s) |
| **SPA serving** | ✅ Complete | `/` route serves `ui/dist/index.html`; 404 fallback for client-side routing |

### SwarmSim Service

| Feature | Status | Details |
|---------|--------|---------|
| **Drone simulation** | ✅ Complete | 10-17 virtual drones (SIM-### namespace); roles per DEFAULT_ROLES; 1 Hz telemetry (0.5 Hz if >15 drones) with ±50ms jitter |
| **Battery drain** | ✅ Complete | ~0.5%/min; start 85-95% random; warn at <20%; 0% → DEAD status |
| **Formation offsets** | ✅ Complete | LEADER (0,0), WINGMAN (±30m lateral), SCOUT (60m), POINT_MAN (45m forward), RELAY/GUARD/CARGO (trailing) |
| **Command handling** | ✅ Complete | Subscribe to `fleet/SIM-+/command`; simulate 100-300ms latency; publish ACK to `fleet/system/command_ack` |
| **Failure simulation** | ✅ Complete | SIM_FAIL_RATE env var (default 2%); random ACK failures for realism |
| **Formation monitoring** | ✅ Complete | Detect >40% OOF for >10s; emit FORMATION_COMPROMISED event |
| **Docker integration** | ✅ Complete | Dockerfile + requirements.txt; docker-compose service with healthcheck on mosquitto |

### Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| **docker-compose** | ✅ Complete | Added swarmsim service; mosquitto, influxdb, grafana, telegraf, inventory, mission-control remain |
| **MQTT topics** | ✅ Complete | `fleet/{id}/telemetry`, `fleet/{id}/command`, `fleet/system/command_ack` per spec |
| **ID namespacing** | ✅ Complete | SIM-###, SITL-###, HW-### supported; socket.js + backend enforce stale detection |

---

## 0.6) Remaining Work (Post-Implementation)

### Integration Testing (Next Steps)

1. **E2E test scenario** (repeatable demo)
   - Start: `docker-compose up` (mosquitto, mission-control, swarmsim)
   - Open: `http://localhost:5000/`
   - Plan: PATROL mission with 12 drones
   - Verify: telemetry updates, marker motion, command ACKs, command queue status
   - Verify: formation break (pause mission when leader HOLD-ed)
   - Verify: reassign leader, resume mission
   - Verify: event timeline shows all state transitions

2. **Backend migration** (existing `poc/mission_control.py` → `mission_control_v3.py`)
   - Backup V2 code
   - Update docker-compose to use mission_control_v3.py
   - Verify SITL drones still work (backward compat)
   - Test SITL + SwarmSim hybrid fleet

3. **UI Polish** (demo readiness)
   - Test zoom/pan on map with 20 drones
   - Verify cluster/thin trails at high drone counts
   - Test command queue scroll at high command volume
   - Verify confirm dialogs on destructive commands (DISABLE/LAND/RETURN)
   - Test mission reset flow

4. **Documentation** (M7: Demo runbook)
   - Write quickstart guide: setup, start, plan mission, observe telemetry
   - Record short screencast of mission lifecycle
   - Document SwarmSim scenario config (seeding, repeatable)

### Hardware Path (Phase 2, Post-Demo)

- **Edge Agent** (`edge_agent/` directory)
  - MAVLink serial/UDP adapter
  - MQTT client with TLS
  - Command → MAVLink translation
  - Telemetry → MQTT publish
  
- **Inventory registry** (evolve from service)
  - Replace MAVLink discovery with Edge Agent heartbeats
  - Metadata cache (drone model, firmware, etc.)
  - Health/last_seen tracking

- **Security** (TLS + auth)
  - TLS MQTT broker config
  - Per-drone API keys or certificates
  - Command allowlist per role

### Future Enhancements (Nice-to-Have)

- Offline map tiles (local GeoTIFF or MBTiles)
- Geofence enforcement (no-fly zones visualized)
- Terrain elevation import for collision avoidance
- Autopilot firmware flashing UI
- Mission history replay (saved missions + telemetry playback)

---

**Principle:** Mission Control stays MQTT + WebSocket centric. Vehicle connectivity is provided by adapters (SITL bridge today; Edge Agent for hardware later).

### V3.0 Demo Mode (Hybrid SwarmSim + SITL)

```
Browser UI (React + Vite SPA)
  - HTTPS + WebSocket (Socket.IO)
        |
        v
Mission Control API
  - REST + WebSocket events
  - MQTT pub/sub
        |
        v
MQTT Broker (Mosquitto)
  - fleet/{id}/telemetry
  - fleet/{id}/command
  - fleet/system/command_ack
        |
        +--> SwarmSim (10-17 virtual drones)
        |     - publishes telemetry + responds to commands
        |
        +--> Inventory Service (SITL bridge + roster)
              - MAVLink TCP to ops-drone-* (3-5 drones)
              - publishes telemetry + ACKs
```

### V3.1 Hardware Mode (Real Drones)

```
Browser UI (React + Vite SPA)
  - HTTPS + WebSocket (Socket.IO)
        |
        v
Mission Control API
  - REST + WebSocket events
  - MQTT pub/sub
        |
        v
MQTT Broker (TLS)
  - fleet/{id}/telemetry
  - fleet/{id}/command
  - fleet/system/command_ack
        |
        +--> Edge Agent (per drone or per vehicle group)
        |     - MAVLink serial/UDP to autopilot
        |     - translates MQTT <-> MAVLink
        |
        +--> Inventory Service (registry + health)
              - roster + metadata + last_seen
```

**Key changes from V2:**
- New React + Vite SPA (no runtime CDN; tiles provider config).
- Mission planning in the UI (PATROL waypoints, PERIMETER geofence, ESCORT route).
- Per-drone and swarm commands with manual confirm + ACK/timeout tracking.
- Hexagonal architecture with ports/adapters so ArduPilot works now and PX4 can be added later.

---

## 2) Workstreams & Deliverables

### A) Protocol & Schema (Week 1)
**Deliverables**
- API contract: `.context/project/docs/19_v3_api_contract.md`
- Mission planning protocol: `.context/project/docs/20_v3_mission_planning_protocol.md`
- Command state machine: `.context/project/docs/21_v3_command_state_machine.md`
- Swarm behavior spec: `.context/project/docs/22_v3_swarm_behavior.md`
- JSON schema updates for telemetry + commands + ACKs (if needed)
**Decisions**
- Required vs optional telemetry fields
- ACK timeout and retry strategy

### B) Edge Agent (Weeks 2-3, post-demo)
**Deliverables**
- `edge_agent/` (new service)
  - MAVLink adapter (serial/UDP)
  - MQTT adapter (TLS)
  - Command routing + ACK
  - Telemetry normalization + publish
- Minimal config: `edge_agent/config.example.yml`
**Notes**
- Start with single-drone agent; support multi-drone later.

### C) Mission Control Backend Updates (Week 3)
**Deliverables**
- Align command/ACK handling with v3 protocol
- Add explicit **command state machine** (requested -> acked -> timed-out)
- Add **telemetry validation** (lat/lon presence, timestamps)

### D) SPA UI (Weeks 4-5)
**Deliverables**
- `ui/` (React + Vite)
  - Map + drone overlays + layers
  - Fleet roster (inventory + telemetry-only drones) + selection
  - Per-drone + bulk commands (confirm + cmd_group_id) + command queue
  - Mission planning tools (PATROL waypoints, PERIMETER geofence, ESCORT route)
  - Timeline/charts (altitude, battery) for demo
- Map tiles provider config (online OSM now; local/offline later)
- No runtime CDN: bundle JS/CSS deps in the build

### E) SwarmSim (Demo Scale, Weeks 4-5)
**Deliverables**
- SwarmSim service (Python) to simulate 10-17 "virtual drones"
  - Publishes `fleet/{id}/telemetry` (1-2 Hz) with stable IDs + roles
  - Subscribes `fleet/+/command` and returns `fleet/system/command_ack`
  - Implements basic formation + mission following so the map looks alive
  - Supports PATROL (waypoints), PERIMETER (geofence patrol), ESCORT (route following)
- Scenario config (seeded/repeatable) for demos

### F) Inventory Service Refactor (Week 5)
**Deliverables**
- Inventory becomes registry + "seen drones" (roster + last_seen + metadata)
- Optionally ingest Edge Agent heartbeat topics
**Notes**
- Keep MAVLink discovery optional for SITL backwards-compat.

### G) Observability (Week 6)
**Deliverables**
- Grafana dashboard updates
- Basic **command metrics** (ack latency, success rate)

### H) Security & Deployment (Week 6)
**Deliverables**
- TLS MQTT config
- Per-drone credentials
- Role-based command allowlists

---

## 3) V3 Telemetry Minimum (Dashboard)

**Required (minimum)**
- `drone_id`
- `timestamp` (unix epoch)
- `latitude`, `longitude`, `altitude_m`
- `battery_pct`
- `status` (ACTIVE/DISABLED/UNKNOWN)
- `mode` (AUTO/RTL/HOLD/UNKNOWN)
- `armed` (true/false)

**Optional (nice-to-have, not required)**
- `velocity_mps`
- `gps_fix`, `satellites_visible`
- `mission_role`

---

## 4) Command Approval Workflow (Manual Confirm)

**Always require confirm**
- `DISABLE/LAND`
- `RETURN/RTL`
- `CLEAR_MISSION`
- Any **bulk** command (selected swarm or all drones)

**No confirm (one-click)**
- `HOLD`
- `ARM/ENABLE`
- `SET_ROLE`

**Individual + Swarm Commands**
- UI must support **per-drone actions** and **common actions** for a selected swarm/all.
- Backend publishes **one command per drone**, with a shared `cmd_group_id` for bulk actions to track a single operator approval.

### MQTT message shape (minimum)

**Command** (published to `fleet/{drone_id}/command`)
```json
{
  "cmd_id": "uuid",
  "cmd_group_id": "uuid (optional, for bulk)",
  "drone_id": "D001",
  "command": "HOLD|RETURN|DISABLE|ARM|DISARM|ENABLE|SET_ROLE|UPLOAD_MISSION|CLEAR_MISSION",
  "params": {},
  "timestamp": 1700000000.0
}
```

**Command params (minimum)**
- `SET_ROLE`: `{"role":"LEADER|POINT_MAN|WINGMAN|SCOUT|RELAY|GUARD|CARGO"}`
- `UPLOAD_MISSION`: `{"waypoints":[{"lat":12.34,"lon":56.78,"alt_m":50.0}]}`
- Other commands: `{}`

**ACK** (published to `fleet/system/command_ack`)
```json
{
  "cmd_id": "uuid",
  "cmd_group_id": "uuid (optional)",
  "drone_id": "D001",
  "command": "HOLD",
  "result": "SUCCESS|FAILED|TIMEOUT",
  "detail": "optional string",
  "timestamp": 1700000001.2
}
```

**Timeout policy**
- Mission Control marks `TIMEOUT` if no ACK is received within N seconds (configurable) and shows it in the command queue.

---

## 5) Migration Plan (V2 -> V3)

**Phase 1 (V3 demo):** Keep SITL in Docker with the existing inventory MAVLink bridge, add SwarmSim for scale, and switch the UI to the React + Vite SPA.  
**Phase 2 (hardware path):** Introduce Edge Agent(s) for real drones (serial/UDP MAVLink) and enable TLS MQTT; inventory becomes registry + health.  
**Phase 3 (cleanup):** Deprecate MAVLink logic inside `inventory/app.py` once Edge Agent is proven (optional).

---

## 6) Acceptance Criteria

1. SPA loads with a working map; tile provider is configurable (online OSM now, local/offline later) with no code changes.
2. Demo shows 5-20 drones simultaneously (hybrid SwarmSim + SITL) with role-colored markers and trails.
3. Operator can plan missions on the map:
   - PATROL: add/edit waypoints and publish.
   - PERIMETER: draw/edit a geofence polygon and publish.
   - ESCORT: draw/edit an asset route and publish.
4. Per-drone commands (HOLD/RETURN/LAND/ENABLE/SET_ROLE) produce ACK/TIMEOUT and update the map state.
5. Bulk swarm commands confirm once and track progress via `cmd_group_id`.
6. Command queue + event timeline reflect ACK/FAILED/TIMEOUT within N seconds (configurable).
7. Hardware path: Mission Control UI/API work without code changes when drone source swaps from SITL bridge to Edge Agent + real drone.
8. Security (hardware path): TLS MQTT is enabled and commands are rejected without valid credentials.

---

## 7) Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| MAVLink link instability | Command loss | ACK + retry + autopilot failsafes (RTL/land) |
| Broker auth misconfig | No fleet visibility | Simple "local dev" and "prod" profiles + health checks |
| SITL scale on laptop | Unstable demo | Hybrid SwarmSim (most drones) + a few SITL drones |
| UI perf at 5-20 drones | Laggy map | Throttle telemetry renders; cap trail points; optional marker clustering |
| External tiles unreachable | Black map | Configurable tiles provider; local tiles later; no runtime CDN |

---

## 8) Decisions (Locked for V3)

- UI: React + Vite SPA (see `.context/project/docs/18_v3_ui_spec.md`).
- Demo target: 5-20 drones on one laptop (hybrid SwarmSim 10-17 + SITL 3-5).
- Internet: allowed for the demo; keep an airgapped path via configurable tile providers; no runtime CDN dependencies.
- Protocol: MQTT topics stay stable (`fleet/{id}/telemetry`, `fleet/{id}/command`, `fleet/system/command_ack`); bulk actions use `cmd_group_id`.
- Inventory: enforce ID namespaces (SIM-/SITL-/HW-) and mark stale if `last_seen` > STALE_SEC (default 30s).
- Autopilot scope: ArduPilot now; PX4 later via adapter behind the same ports.
- Telemetry minimum defined in section **3**.
- Command approval: manual confirm as defined in section **4** (per-drone + bulk supported).
- Formation behavior: per-drone HOLD/RTL/LAND breaks formation for that drone; UI must visualize the divergence.
- Hardware path: add Edge Agent post-demo; inventory evolves to registry + health.
