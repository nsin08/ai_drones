# Mission Control v4 Sprint Planning

## Current v3 Drawbacks (Real Challenges Ahead)

### 🔴 **Critical Issues**

#### 1. No Hardware Safety Enforcement
**Problem:** Real drones can execute dangerous commands without preflight checks.
- Command: "arm drone" succeeds even if GPS: no fix, EKF: unhealthy, battery: 5%
- No mode validation: can't arm in MANUAL mode, but v3 doesn't check
- No geofence or failsafe enforcement in backend

**v4 Fix:** Prearm health checks + command validation
- GET `/api/drone/{id}/preflight` → {gps_ok, ekf_ok, battery_pct, mode, armed, can_arm: bool}
- Command validator: checks drone prearm state before accepting ARM command
- Safety interlock: DISARM enforced if battery < threshold OR geofence breach

---

#### 2. Commands Time Out & Disappear
**Problem:** Commands have no retry logic; timeout = "oh well"; no history.
- Send ARM → REQUESTED (5s timeout) → TIMED_OUT → buried in event ring
- User doesn't know if command was lost in MQTT or drone ignored it
- No way to re-issue command or check last state

**v4 Fix:** Command retry + audit trail
- `cmd_status = {REQUESTED → [RETRYING (up to 3×)] → ACKED/TIMED_OUT/FAILED}`
- Persistent command log (PostgreSQL/SQLite) with full history
- GET `/api/commands?drone_id=HW-001&limit=50` → recent + retried commands
- UI shows "retry pending" state

---

#### 3. Only 1 Mission at a Time (Rigid)
**Problem:** Can't run patrol + escort simultaneously or compose missions from sub-tasks.
- `mission_state = "IDLE" → PLANNING → PLANNED → ACTIVE → PAUSED → COMPLETED`
- All drones locked to a single mission_type
- No way to say "drone A does PATROL" + "drone B does PERIMETER" concurrently

**v4 Fix:** Multi-mission + hierarchical task decomposition
- Mission v4 structure: `{ id, type, status, tasks: [ {task_id, drone_ids, type, state, waypoints} ] }`
- Each drone assigns to (mission_id, task_id, role) tuple
- Pub/Sub per task: drones track own task progress independently
- PAUSED mission = pause all child tasks; RESUMED = restore state

---

#### 4. Monitor-Only Map (No Interaction)
**Problem:** Operators can't plan missions from the UI; all planning is backend-only code.
- Map shows drone icons only; drag-to-create-waypoint disabled
- MissionSetup is a JSON dropdown simulator, not mission builder
- No visual geofence editor

**v4 Fix:** Interactive mission builder
- Drag drone icon or waypoint on map → triggers `/api/mission/add_waypoint` 
- Click+drag geofence polygon → serializes to MQTT
- Formation shapes (V, line, circle) selectable from UI → sent to drones
- Undo/redo support for mission edits

---

### ⚠️ **Scaling Issues**

#### 5. In-Memory State (Can't Persit)
**Problem:** Restart → lose all command history, mission state, events.
- `commands = {}` dictionary is ephemeral
- Event ring buffer (200 max) = no audit trail
- Cluster deployment = no shared state across instances

**v4 Fix:** Event sourcing + database
- SQLAlchemy models: Command, Event, Mission, DroneMetric
- Event log: immutable stream of {event_id, type, drone_id, timestamp, data}
- DB replicas: read-heavy queries (history, analytics) off-load to read-only
- Mission state rebuilt from event log on restart

---

#### 6. Stale Drone Detection is Too Simple
**Problem:** `last_seen > 30s` = STALE; no health scoring or alert thresholds.
- Drone with battery=2% shows as ACTIVE (not yellow/red warning)
- No distinction: "lost signal" vs "battery low" vs "mode mismatch"
- UI can't prioritize which drones need attention

**v4 Fix:** Health scoring + alerting
- Drone health = min(battery_score, gps_score, ekf_score, signal_score) ∈ [0, 1]
  - battery < 10% → red
  - gps < 4 satellites → yellow
  - EKF unhealthy → critical
  - last_seen > timeout → offline
- Alerts: push critical events to UI; sound/badge notification
- GET `/api/fleet/health` → {healthy: 8, warning: 2, critical: 1, offline: 0}

---

#### 7. No Real-Time Command Feedback
**Problem:** User sends "hold" but doesn't see drone actually holding until telemetry update.
- Command ACKED doesn't mean drone is in HOLD mode yet
- No intermediate telemetry validation (e.g., "accelerometer detected hold")
- UI shows command state, not drone actual state → confusing

**v4 Fix:** State machine + telemetry-driven validation
- Command: ARM → drone mode must transition to GUIDED within 2s
- If transition fails → FAILED state + alert "Drone rejected command"
- Telemetry updates feed mode/armed directly; UI binds to actual state, not command state
- GET `/api/drone/{id}` includes `last_command_acked` + `actual_state`

---

### 📊 **Missing Operations Features**

#### 8. No Multi-User Support
**Problem:** Single operator; no handoff, no concurrent UI sessions, no role-based access.
- Anyone with URL access can execute commands
- No audit trail of "who commanded what"
- No permission model (e.g., only ops-lead can arm)

**v4 Fix:** Auth + audit
- JWT tokens: operator_id, role (PILOT, OBSERVER, ADMIN)
- Command log includes `issued_by: operator_id`
- Command endpoint checks: `if role != PILOT: reject ARM`
- Concurrent client broadcast: "Pilot A is flying mission X; Pilot B is observing"

---

#### 9. No Graceful Degradation
**Problem:** If MQTT broker down or Inventory service slow → UI hangs or shows stale data.
- MQTT disconnect = no telemetry updates; UI doesn't warn
- Inventory timeout = slow roster load (timeouts stack)
- No fallback: "serve last-known state if upstream unavailable"

**v4 Fix:** Circuit breaker + service layer
- MQTT reconnect BackoffStrategy: 1s → 5s → 30s (exponential)
- Inventory service wrapped in circuit breaker: fail-fast after 3 errors
- UI displays "MQTT: OFFLINE (cached data)" badge
- Serve drone_states from cache if real-time unavailable

---

#### 10. No Test/Prod Environment Separation
**Problem:** Same docker-compose runs SIM + REAL drones; easy to confuse + dangerous.
- Simulator drones (SIM-001) mixed with real drones (HW-001)
- Both publish to same `fleet/+/telemetry` topic
- Can accidentally command real drone thinking it's simulator

**v4 Fix:** Environment-based message routing
- MQTT topic filtering: `fleet/{env}/{drone_id}/telemetry` (env=sim|prod|lab)
- UI filter mode: "Show SIM only | PROD only | ALL"
- Backend config: `DRONE_ENV=prod` → reject commands to SIM-* drones
- SwarmSim publishes to `fleet/sim/SIM-*/telemetry` only

---

## Proposed v4 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Mission Control v4                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  React UI    │  │  WebSocket   │  │  REST API    │  │  gRPC or   │ │
│  │  (Vite)      │  │  (SocketIO)  │  │  (Flask)     │  │  FastAPI   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │
│         │                 │                  │                │         │
│         └─────────────────┴──────────────────┴────────────────┘         │
│                              │                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Command Validator Layer                                   │        │
│  │  - Preflight checks (health, mode, battery, geofence)     │        │
│  │  - ACL check (role-based)                                 │        │
│  │  - Retry logic + timeout handling                         │        │
│  └────────────────────────────────────────────────────────────┘        │
│                              │                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  State Machine Engine (Multi-Mission)                      │        │
│  │  - Mission { id, tasks: [{task_id, drones, state}] }      │        │
│  │  - Task FSM: PLANNED → ACTIVE → PAUSED | COMPLETED        │        │
│  │  - Drone role assignment per task                         │        │
│  └────────────────────────────────────────────────────────────┘        │
│                              │                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Event Sourcing + Persistent Log                           │        │
│  │  - Immutable event stream (database)                       │        │
│  │  - Cache: recent commands + drone states                  │        │
│  │  - Query: history, audit trail, state rebuild             │        │
│  └────────────────────────────────────────────────────────────┘        │
│                              │                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │  MQTT Pub    │  │  Inventory   │  │  Database    │                 │
│  │  (+ Broker)  │  │  (Inv. API)  │  │  (SQLAlchemy)│                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Telemetry + Health Scoring                                │        │
│  │  - Source-aware: SIM vs EDGE_AGENT vs SITL                │        │
│  │  - Metric aggregation: battery, GPS, EKF, signal         │        │
│  │  - Alert threshold evaluation                             │        │
│  └────────────────────────────────────────────────────────────┘        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## v4 Sprint Tasks

### Phase 1: Foundation (Weeks 1-2)

**S4-001: Database Setup**
- [ ] PostgreSQL schema: Command, Event, Mission, Drone, Operator tables
- [ ] SQLAlchemy ORM + migrations (Alembic)
- [ ] Seed with test data (10 SIM drones, 2 HW drones)
- [ ] DoD: `pytest` passes, migrations reversible, schema documented

**S4-002: Event Sourcing Backend**
- [ ] EventLog table + append-only writes
- [ ] Event types: COMMAND_REQUESTED, COMMAND_ACKED, COMMAND_FAILED, TELEMETRY_RECEIVED, MISSION_*
- [ ] Snapshot table for state reconstruction (every 100 events)
- [ ] DoD: 100 events/sec throughput, rebuild from log in <1s

**S4-003: Command Validator + Retry**
- [ ] Preflight check endpoint: GET `/api/drone/{id}/preflight`
- [ ] Command validator middleware: checks prearm, ACL, battery, geofence
- [ ] Retry logic: up to 3 retries with exponential backoff
- [ ] DoD: ARM rejected if battery < 10%, EKF unhealthy, or no GPS fix

### Phase 2: Mission Model (Weeks 3-4)

**S4-004: Multi-Mission State Machine**
- [ ] Mission v4 schema: `{ id, type, status, tasks: List[Task], config }`
- [ ] Task schema: `{ task_id, drone_ids, type, state, waypoints, formation }`
- [ ] FSM: IDLE → PLANNING → PLANNED → ACTIVE / PAUSED → COMPLETED / ABORTED
- [ ] Endpoint: POST `/api/mission/create` + `/api/mission/{id}/start`
- [ ] DoD: concurrent missions runnable, each with independent task progress

**S4-005: Drone Health Scoring**
- [ ] Health metric = f(battery%, GPS sats, EKF status, signal_age)
- [ ] Thresholds: RED < 0.3, YELLOW < 0.7, GREEN ≥ 0.7
- [ ] Endpoint: GET `/api/fleet/health` + `/api/drone/{id}/health`
- [ ] DoD: dashboard shows drones color-coded by health

### Phase 3: UI + Real-Time Feedback (Weeks 5-6)

**S4-006: Interactive Mission Builder**
- [ ] Map: drag drone icon → add waypoint
- [ ] Geofence polygon editor (draw on map)
- [ ] Formation selector (V, line, circle)
- [ ] Real-time validation: shows if waypoint inside geofence
- [ ] DoD: create + save PATROL mission with 5 waypoints from UI

**S4-007: Command Feedback UX**
- [ ] State display v2: actual_state (from telemetry) + pending_command
- [ ] Timeline: "commanded ARM (pending) → ACKED → mode: GUIDED (actual)"
- [ ] Alert modal for CRITICAL events (battery low, EKF fail, prearm reject)
- [ ] DoD: user sees real-time confirmation that drone executed command

**S4-008: Auth + Audit**
- [ ] JWT token generation (operator_id, role: PILOT|OBSERVER|ADMIN)
- [ ] Login page + session persistence
- [ ] Command ACL: OBSERVER can view only; PILOT can command; ADMIN unrestricted
- [ ] Command log: `/api/commands?issued_by=op_001` → shows operator history
- [ ] DoD: two users, different roles, can control same UI independently

### Phase 4: Reliability (Weeks 7-8)

**S4-009: Circuit Breaker + Graceful Degradation**
- [ ] MQTT reconnect strategy: exponential backoff (1s → 5s → 30s)
- [ ] Inventory service wrapped in circuit breaker (fail-fast after 3 errors)
- [ ] UI shows "OFFLINE (cached)" badge when Inventory unavailable
- [ ] Serve last-known drone states from DB if live unavailable
- [ ] DoD: simulate MQTT broker crash; UI remains interactive with cached data

**S4-010: Environment Separation (Test/Prod)**
- [ ] MQTT topics: `fleet/{env}/{drone_id}/telemetry` (env=sim|prod)
- [ ] Backend config: `DRONE_ENV=prod` only accepts HW-* commands
- [ ] UI toggle: "Show SIM | PROD | ALL" drone filter
- [ ] Docker compose: hardware.yml uses ENV_MODE=prod by default
- [ ] DoD: SIM and PROD drones visible in different tabs; can't arm SIM while prod="true"

**S4-011: Integration + Stress Testing**
- [ ] Load test: 50 drones, 5 concurrent mission ops
- [ ] Chaos test: simulate MQTT broker restart, DB failover
- [ ] Regression tests: v3 features still work (roster, basic commands)
- [ ] DoD: sustained 100 events/sec, <100ms UI latency

### Phase 5: Documentation + Handoff (Week 9)

**S4-012: Architecture Docs + Runbook**
- [ ] v4 Design Doc: state machine, event sourcing, API contracts
- [ ] Migration guide: v3 → v4 (backward-compat layer if needed)
- [ ] Operator runbook: common scenarios (armed drone lost signal, prearm fail, mission pause)
- [ ] DoD: new operator can connect real drone + run PATROL mission in <30 min

---

## Tech Stack Recommendation

| Component | v3 | v4 | Reason |
|-----------|----|----|--------|
| Backend | Flask | **FastAPI** | async/await, built-in OpenAPI, better for high concurrency |
| Real-time | SocketIO | **WebSocket + Redis Pub/Sub** | horizontal scaling, decoupled from API |
| Database | In-memory | **PostgreSQL + SQLAlchemy** | persistence, event sourcing, audit trail |
| Auth | None | **Python-jose JW tokens** | stateless, operator attribution |
| Broker | Mosquit to (passive) | **Mosquitto** (active circuit breaker) | add reconnect management in Python |
| Load Testing | None | **Locust** | replay real drone behaviors |

---

## Success Metrics

- ✅ 0 critical bugs in hardware command path
- ✅ ARM command rejected if preflight check fails
- ✅ 5-drone concurrent missions working simultaneously
- ✅ Command retry succeeds in 90% of timeout cases
- ✅ <100ms UI update latency (p99) at 50 drones
- ✅ Full audit trail for all drone commands
- ✅ Two operators can use UI independently with different roles

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| **Migration burden:** Rewrite backend logic | Keep v3 running in parallel; gradual migration of endpoints |
| **Database bottleneck:** Event log grows unbounded | Partition by drone_id + time; archive old events |
| **Auth complexity:** JWT management overhead | Use industry library (python-jose); start simple (no refresh tokens) |
| **Hardware unpredictability:** Real drones don't follow state machine | Telemetry-driven state validation; accept "mode mismatch" alerts |

