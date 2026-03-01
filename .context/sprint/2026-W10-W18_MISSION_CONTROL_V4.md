# Sprint 2026-W10 to W18: Mission Control v4 Development Track

**Dates:** 2026-03-03 to 2026-04-28 (9 weeks)  
**Document Type:** Mission Control v4 — Hardware Safety, Persistence, Multi-Mission  
**Branch:** `feature/mission-control-v4`  
**Program Horizon:** W10-W18 (v3 → v4 migration track)

---

## Goals

- Deliver production-ready mission control backend with mandatory preflight safety checks before any drone command execution
- Replace ephemeral in-memory state with persistent PostgreSQL event sourcing for full audit trail and command retry
- Enable concurrent multi-mission execution with task decomposition and per-drone role assignment
- Provide operators with interactive mission builder UI for drag-to-waypoint planning
- Implement role-based access control (PILOT/OBSERVER/ADMIN) with operator attribution for all commands
- Establish reliability patterns: circuit breaker for MQTT/Inventory, graceful degradation, environment separation (SIM vs PROD)

---

## Product Outcomes (Business)

| Outcome | Current (v3) | Target by W18 End |
|---|---|---|
| Hardware Safety | Commands execute without validation | 100% of commands require preflight check; dangerous commands rejected upfront |
| Command Persistence | Timeout = lost forever | 100% queryable history; 90%+ retry success on timeout |
| Mission Concurrency | 1 mission at a time | 5+ concurrent missions, independent per-drone tasks |
| UI Interactivity | Display-only map | Drag-to-waypoint, geofence editor, formation selector, mission timeline |
| Data Persistence | Restart = lost all history | Full event sourcing; state rebuilt from log in <1s |
| Access Control | Open to anyone | JWT auth + 3 roles; audit trail shows who commanded what |
| Reliability | MQTT down = froze | Graceful degradation; fallback to cached state |
| Fleet Scale | 1-4 drones tested | 50+ drones supported; <100ms UI latency (p99) |

---

## Background: v3 Production Gaps

v3 works well for POC-2 (real hardware demo, single drone). But operational deployment exposes 10 critical gaps:

1. **No hardware safety checks** — ARM command succeeds even with battery=5%, EKF unhealthy, GPS: no fix. Dangerous for real hardware.
2. **Commands disappear on timeout** — MQTT publish → wait 5s → TIMED_OUT → event buried in ring buffer. No retry, no recovery.
3. **Single mission only** — All drones locked to one mission. Can't run PATROL + ESCORT concurrently on different drones.
4. **Monitor-only UI** — Operators can't plan missions interactively; all planning is backend-only code.
5. **In-memory state** — Restart → lose all command history, mission state, events. No audit trail.
6. **Stale detection is crude** — `last_seen > 30s = STALE`; doesn't distinguish battery low vs signal loss vs EKF fail.
7. **No real command feedback** — Command ACKED != drone actually executed it. User sees command state, not drone actual state.
8. **No multi-user support** — Anyone with URL can command drones. No operator attribution, no role-based ACL.
9. **No graceful degradation** — MQTT broker down or Inventory timeout → UI hangs.
10. **SIM/PROD mixed** — Easy to accidentally command real drone thinking it's simulator.

---

## Scope

### P0 In Scope (W10-W18)

**Phase 1: Foundation (W10-W11)**
- S4-001: PostreSQL + SQLAlchemy + migrations (events, commands, missions, operators)
- S4-002: Event sourcing backend (immutable log, snapshot rebuild)
- S4-003: Command validator + retry logic (preflight checks, 3x retry, exponential backoff)

**Phase 2: Mission Model (W12-W13)**
- S4-004: Multi-mission state machine with task decomposition
- S4-005: Drone health scoring (battery, GPS, EKF, signal) + alert thresholds

**Phase 3: UI + Auth (W14-W15)**
- S4-006: Interactive mission builder (drag waypoints, geofence, formations)
- S4-007: Command feedback UX (state timeline, alert modals)
- S4-008: JWT auth + role-based ACL + operator audit

**Phase 4: Reliability (W16-W17)**
- S4-009: Circuit breaker + graceful degradation (MQTT/Inventory)
- S4-010: Environment separation (SIM vs PROD via topic routing)
- S4-011: Load testing + chaos (50 drones, concurrent missions, MQTT restart)

**Phase 5: Polish + Docs (W18)**
- S4-012: Architecture docs, operator runbook, migration guide v3→v4

### P1 Deferred (Post-W18)

- Real OAuth2 (GitHub, Google) — using demo hardcoded credentials for W10-W18
- Cluster deployment (Kubernetes) + horizontal scaling — single-region Docker Compose for W10-W18
- Advanced graph analytics (pattern detection, anomaly scoring) — basic health scoring only for W10-W18
- Mobile app companion
- Push notifications to operators

---

## Architecture

### v4 Core Stack

```
┌─────────────────────────────────────────────────────────┐
│  React UI (Vite)                                        │
│  - Interactive mission builder                          │
│  - Command timeline + state display                     │
│  - Fleet health dashboard (color-coded by score)        │
│  - Multi-user concurrent browsing (WebSocket broadcast) │
└──────────────────┬──────────────────────────────────────┘
                   │ WebSocket (JWT auth, SocketIO)
┌─────────────────────────────────────────────────────────┐
│  FastAPI Backend (Async)                                │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐│
│  │ Command Router + Validator Layer                    ││
│  │ - Preflight check middleware (battery, GPS, EKF)    ││
│  │ - ACL check (role-based)                            ││
│  │ - Retry logic (3x with exponential backoff)         ││
│  │ - Emit event → database (immutable log)             ││
│  └─────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │ Multi-Mission State Machine                         ││
│  │ - Mission { id, type, tasks: [Task] }               ││
│  │ - Task FSM: PLANNED→ACTIVE→PAUSED→COMPLETED        ││
│  │ - Per-drone role assignment (task-specific)         ││
│  │ - Task progress tracking + rollback on interrupt    ││
│  └─────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │ Event Sourcing + Health Scoring                     ││
│  │ - Immutable event log (append-only)                 ││
│  │ - Snapshot every 100 events for state rebuild       ││
│  │ - Telemetry → health metric aggregation             ││
│  │ - Alert threshold evaluation (RED/YELLOW/GREEN)     ││
│  └─────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │ Auth + Audit                                        ││
│  │ - JWT token generation (operator_id, role, scope)   ││
│  │ - Command ACL: OBSERVER (view-only), PILOT          ││
│  │   (command assigned drones), ADMIN (unrestricted)   ││
│  │ - Operator attribution on all events                ││
│  └─────────────────────────────────────────────────────┘│
└────────┬────────────────────────────────────┬────────────┘
         │ MQTT                               │ SQL
    ┌────────────┐              ┌──────────────────────┐
    │ Mosquitto  │              │ PostgreSQL 15+       │
    │ Broker     │              │ - events (immutable) │
    │ (pub/sub)  │              │ - commands (with ACL)│
    └────────────┘              │ - missions & tasks   │
                                │ - drone_metrics      │
                                │ - operators & roles  │
                                │ - audit_log          │
                                └──────────────────────┘
```

### Tech Stack

| Component | v3 | v4 | Why |
|-----------|----|----|-----|
| Backend API | Flask (sync) | **FastAPI** (async) | Built-in OpenAPI, better concurrency, streaming responses |
| Database | In-memory dict | **PostgreSQL 15** | ACID transactions, event sourcing, full-text search, JSONB |
| ORM | None | **SQLAlchemy 2.0** | Type-safe, migrations (Alembic), relationships |
| Real-time | SocketIO | **WebSocket + SocketIO** (same, but with DB backing) | Persist session state for reconnect recovery |
| Auth | None | **PyJWT + python-jose** | Stateless tokens, operator attribution |
| Load Testing | Manual | **Locust** | Replay real drone behaviors, stress test command handling |
| Metrics | None | **Prometheus** (optional W19) | Dashboard latency, MQTT message rate, event throughput |

---

## Implementation Work Packages

### WP-01: Database Setup & Event Sourcing Foundation (W10)

**User Story:**  
As a backend developer, I have a PostgreSQL schema with immutable event logging, command tracking, and full-text search so that all mission operations are auditable and recoverable.

**Acceptance Criteria**
- PostgreSQL schema initialized with tables: events, commands, missions, tasks, drone_metrics, operators, audit_log
- Alembic migrations created and tested (can migrate up and down)
- Event types defined: COMMAND_REQUESTED, COMMAND_ACKED, COMMAND_FAILED, TELEMETRY_RECEIVED, MISSION_STARTED, MISSION_PAUSED, MISSION_COMPLETED
- Snapshot table created; snapshot saved every 100 events
- Full-text search index on command remarks + operator notes
- No data loss; 100% of events queryable after restart

**Technical Tasks**
- [ ] Create `alembic/versions/001_init.py` with schema DDL
- [ ] Define SQLAlchemy models: Event, Command, Mission, Task, DroneMetric, Operator, AuditLog
- [ ] Create Event repository with `append()` and `query_range(drone_id, start_time, end_time)`
- [ ] Implement snapshot logic: trigger every 100 events, save to snapshot table
- [ ] Implement state rebuild from snapshot + replayed events (test: 10,000 event replay < 1s)
- [ ] Write Pytest fixtures for DB setup/teardown
- [ ] Document schema in `.context/project/V4_DATABASE_SCHEMA.md`

**Definition of Done**
- [ ] Schema deployed to test PostgreSQL
- [ ] Alembic up/down migrations verified
- [ ] pytest passes on event append/query/snapshot/rebuild
- [ ] Stress test: 10k events inserted and queried in <5s

---

### WP-02: Command Validator & Retry Logic (W10-W11)

**User Story:**  
As an operator, when I send "ARM" to a drone, the system validates preflight health (battery, GPS, EKF) before executing. If the command times out, it retries up to 3 times automatically.

**Acceptance Criteria**
- GET `/api/drone/{id}/preflight` returns: {battery_pct, gps_fix, ekf_ok, mode, armed, prearm_failures: [string], can_arm: bool}
- POST `/api/command/arm` rejects if `preflight.can_arm == false` with reason
- ARM rejected if battery < 10%, EKF unhealthy, GPS < 4 satellites, or already armed
- Commands retry up to 3× on timeout with exponential backoff (1s, 2s, 4s)
- Command status FSM: REQUESTED → [RETRYING (n=1..3)] → ACKED | TIMED_OUT | FAILED
- Persistent DB log of all attempts (timestamp, retry count, result)

**Technical Tasks**
- [ ] Implement `PreflightChecker` class in `services/preflight.py`
  - Get latest drone telemetry from cache
  - Check battery_pct >= threshold (config: 10%)
  - Check gps: fix >= 3 (not fix=4 required; be practical for some environments)
  - Check ekf_ok from ATTITUDE/EKF messages
  - Return health object with can_arm boolean
- [ ] Implement `CommandValidator` middleware in FastAPI
  - Before routing any command, call preflight check
  - Reject with HTTP 400 if preflight fails, include reason
  - Log rejection to audit_log table
- [ ] Implement retry logic in `services/command_executor.py`
  - Attempt 1: publish to MQTT, wait `ACK_TIMEOUT_SEC`
  - If TIMED_OUT: sleep 1s, attempt 2
  - If TIMED_OUT: sleep 2s, attempt 3
  - If TIMED_OUT after 3: mark FAILED, emit alert
  - Each attempt recorded separately in commands table with `attempt_num`, `sent_epoch`, `result`
- [ ] Write tests for: happy path, battery too low, no GPS, EKF unhealthy, timeout → retry → success, timeout → retry → final fail
- [ ] Document in API spec: `/api/command/{verb}` response codes and retry behavior

**Definition of Done**
- [ ] Preflight endpoint returns correct health status
- [ ] Command rejected with reason if preflight fails
- [ ] ARM with battery=5% rejected (not sent to MQTT)
- [ ] Timeout + retry succeeds (simulated MQTT delay)
- [ ] pytest: 8+ test cases, all passing
- [ ] No command published to MQTT if preflight check fails

---

### WP-03: Multi-Mission State Machine (W12-W13)

**User Story:**  
As a mission planner, I can create multiple missions concurrently (PATROL on drone A, ESCORT on drone B) where each mission has independent tasks and state, and pause one without affecting the other.

**Acceptance Criteria**
- Mission model: `{ id: UUID, type: str, status: str, tasks: [Task], config: dict, created_by: operator_id, created_at: timestamp }`
- Task model: `{ task_id: UUID, mission_id: UUID, drone_ids: [str], type: str, status: str, waypoints: [Waypoint], formation: str, priority: int }`
- Mission FSM: IDLE → PLANNING → PLANNED → ACTIVE → PAUSED → COMPLETED | ABORTED
- Task FSM: PLANNED → ACTIVE → PAUSED → COMPLETED | FAILED
- Each drone tracks own task_id + role per mission (no interference between missions)
- Pause mission M1 → all tasks in M1 paused; mission M2 unaffected
- Resume mission M1 → restore task progress from event log; drones continue from saved checkpoint

**Technical Tasks**
- [ ] Define Mission and Task SQLAlchemy models with relationships
- [ ] Implement mission state machine in `services/mission_fsm.py`
  - State transition methods: `transition_to_planning()`, `plan()`, `start()`, `pause()`, `resume()`, `abort()`
  - Emit MissionStateChanged event on each transition
  - Store in database and broadcast via WebSocket
- [ ] Implement task distribution logic
  - POST `/api/mission/{id}/start` → for each task, publish `fleet/{drone_id}/task` message with waypoints
  - Track which drones assigned to which tasks via `mission_assignments` table
- [ ] Implement checkpoint save on PAUSE
  - Save last_waypoint_index, last_position, elapsed_time per task
  - On RESUME, publish checkpoint message to drones
- [ ] Implement multi-mission concurrency test
  - Create 2 missions with non-overlapping drone_ids
  - Start both, verify independent progress
  - Pause M1, verify M2 continues
  - Resume M1, verify M1 resumes from checkpoint
- [ ] Write tests: 5+ scenarios (concurrent start, selective pause, abort, state rebuild from log)

**Definition of Done**
- [ ] Multiple missions can be in ACTIVE state simultaneously
- [ ] Pause one mission doesn't pause others
- [ ] Task assignment and waypoint distribution working
- [ ] pytest: 6+ test cases, all concurrent scenario tests passing
- [ ] State rebuilds correctly from event log after restart

---

### WP-04: Drone Health Scoring & Alerting (W13)

**User Story:**  
As an operator, I instantly see which drones need attention via color-coded health score (RED=critical, YELLOW=warning, GREEN=healthy) based on battery, GPS, EKF, and signal quality.

**Acceptance Criteria**
- Health metric = min(battery_score, gps_score, ekf_score, signal_score) ∈ [0, 1]
  - battery_score: (pct / 100) clamped to [0, 1]
  - gps_score: (satellites / 10) capped at 1.0; 0 if no fix
  - ekf_score: 1.0 if OK, 0.0 if unhealthy
  - signal_score: (1.0 - (time_since_last_msg / stale_timeout)) clamped to [0, 1]
- Health thresholds: RED if < 0.3, YELLOW if < 0.7, GREEN if ≥ 0.7
- Critical alerts generated when health transitions to RED or YELLOW
- GET `/api/fleet/health` returns: {healthy: int, warning: int, critical: int, offline: int, details: []}
- UI list shows drones color-coded by health; clicking drone shows health breakdown (battery %, GPS sats, EKF, signal age)

**Technical Tasks**
- [ ] Implement HealthScorer class in `services/health_scoring.py`
  - Method: `score_drone(telemetry: Telemetry) -> HealthScore`
  - HealthScore: {overall: float, battery_score, gps_score, ekf_score, signal_score, status: str}
- [ ] Add health scoring to telemetry handler
  - On each telemetry message, call `score_drone()` and save to `drone_metrics` table
  - If status changed (e.g., GREEN → RED), emit AlertGenerated event
- [ ] Implement GET `/api/fleet/health` endpoint
  - Aggregate latest health scores, count by status
  - Return list of drones with scores and breakdowns
- [ ] Implement alert thresholds in config
  - STALE_SEC = 30 (default)
  - BATTERY_CRITICAL_PCT = 10
  - GPS_CRITICAL_SATS = 3
  - EKF_UNHEALTHY = explicit flag from telemetry
- [ ] Update React UI to color-code drone roster by health
  - Green: health >= 0.7
  - Yellow: 0.3 <= health < 0.7, show warning icon
  - Red: health < 0.3, show critical icon
  - Grey: offline (stale)
- [ ] Write tests: 4+ scenarios (battery decline, GPS loss, EKF failure, signal timeout; each tests health transition and alert generation)

**Definition of Done**
- [ ] Health scores calculated and persisted for all telemetry
- [ ] Color-coded roster in UI matches health scores
- [ ] Critical alerts fired when health transitions to RED
- [ ] GET `/api/fleet/health` returns correct counts and details
- [ ] pytest: 5+ test cases passing

---

### WP-05: JWT Auth + Role-Based Access Control (W14)

**User Story:**  
As a fleet operator, I can log in with JWT token and issue commands only to drones assigned to my role (PILOT can fly, OBSERVER can only view, ADMIN unrestricted). All actions are attributed to my operator ID.

**Acceptance Criteria**
- Login endpoint: POST `/api/auth/login` accepts {username, password} → returns JWT token with {operator_id, role, assigned_drones: [str], exp}
- JWT validated on all protected endpoints; missing/expired token → HTTP 401
- Command endpoints check role: OBSERVER rejected with HTTP 403, PILOT/ADMIN allowed (subject to assignment check)
- PILOT can only command drones in their `assigned_drones` list; ADMIN can command all
- All events, commands, audit logs include `operator_id` to show who issued the command
- Demo credentials: admin/fleetedge2026 (ADMIN role, all drones)
- Frontend: login page, logout button, display current operator name in nav

**Technical Tasks**
- [ ] Create Operator and OperatorRole SQLAlchemy models
  - Operator: {id, username, password_hash, role: enum(PILOT, OBSERVER, ADMIN), assigned_drones: List[str], created_at}
  - Seed with admin user (pre-hashed password)
- [ ] Implement OAuth-less auth in `services/auth.py`
  - `hash_password(pwd: str) -> str` using bcrypt
  - `validate_password(pwd: str, hash: str) -> bool`
  - `create_jwt_token(operator: Operator) -> str` with exp=1 day
  - `decode_jwt_token(token: str) -> dict` with validation
- [ ] Implement `/api/auth/login` endpoint
  - Lookup operator by username
  - Validate password hash
  - Return JWT token or 401
- [ ] Implement auth middleware in FastAPI
  - Extract token from Authorization header
  - Decode and validate; set `request.operator` for downstream handlers
  - Reject if expired or invalid
- [ ] Implement role check in command endpoints
  - Retrieve operator from request.operator
  - If OBSERVER: reject with HTTP 403 "read-only role"
  - If PILOT: check if drone_id in operator.assigned_drones; reject if not assigned
  - If ADMIN: allow all
- [ ] Update telemetry/command handlers to record `operator_id`
  - Event.operator_id = request.operator.id
  - Command.issued_by = request.operator.id
- [ ] Create React login page at `/login`
  - Username/password form
  - On success, save JWT to localStorage with key `mission_control_token`
  - Redirect to dashboard
- [ ] Add auth header to all API calls in React
  - axios interceptor or fetch wrapper: `Authorization: Bearer ${token}`
- [ ] Add logout button to nav
  - Clear localStorage, redirect to `/login`
- [ ] Write tests: login success/fail, JWT expiry, role check (observer rejected, pilot assigned, admin allowed), operator attribution

**Definition of Done**
- [ ] Login page functional; demo credentials work
- [ ] JWT persisted in localStorage
- [ ] Protected endpoints reject unauth requests (401)
- [ ] OBSERVER commands rejected (403)
- [ ] PILOT can only command assigned drones
- [ ] ADMIN can command all
- [ ] All events show operator_id
- [ ] pytest: 8+ test cases passing

---

### WP-06: Interactive Mission Builder UI (W14-W15)

**User Story:**  
As a mission planner, I can drag waypoints on the map, draw a geofence polygon, and select formation shapes (V, line, circle) — all from the UI without writing backend code.

**Acceptance Criteria**
- Map shows "Add Waypoint" pin; clicking any location adds waypoint marker with sequence number
- Drag waypoint to reorder; drag to new position updates coordinates
- Draw geofence: click "Draw Geofence" → drag to create polygon → shows if waypoints inside/outside
- Formation selector dropdown: V, LINE, CIRCLE; shows preview on map
- Real-time validation: geofence breach shows warning
- Save button commits mission to database with all waypoints + geofence + formation
- Load button retrieves saved mission and populates map with markers
- Undo/redo support (back/forward buttons) for waypoint edits

**Technical Tasks**
- [ ] Update React map component (`CenterMap.jsx`)
  - Add mode toggle: "View" | "Edit"
  - In Edit mode: map is interactive; click to add waypoint
  - Waypoint markers are draggable; drag updates lat/lon
  - Right-click marker to delete
- [ ] Implement geofence polygon drawing (Leaflet `Draw` plugin)
  - Click "Draw Geofence" enables drawing
  - Visual feedback: geofence shown as semi-transparent polygon
  - Validation: check each waypoint inside/outside
- [ ] Implement formation shape selector
  - Dropdown: V, LINE, CIRCLE
  - Show formation shape preview on map
  - Transmit to drones as `formation` field in task
- [ ] Implement mission plan serialization
  - Collect: mission_type, drone_ids, waypoints, geofence, formation
  - POST `/api/mission/create` with full plan
- [ ] Implement mission loading
  - GET `/api/mission/{id}` returns mission plan
  - Load and display on map (markers, geofence, formation)
- [ ] Implement undo/redo using React context or library (e.g., `zustand`)
  - Track history of waypoint changes
  - Undo/redo buttons restore previous state
- [ ] Write component tests: 5+ scenarios (add waypoint, drag, delete, geofence validation, formation selection)

**Definition of Done**
- [ ] Drag-to-add waypoint works in Edit mode
- [ ] Geofence polygon drawing and validation working
- [ ] Formation shape preview shown on map
- [ ] Mission save persists to database
- [ ] Mission load retrieves and displays on map
- [ ] Undo/redo works for waypoint edits
- [ ] UI tests: 5+ scenarios passing

---

### WP-07: Command Feedback UX + Command Timeline (W15)

**User Story:**  
As an operator, when I send a command to a drone, I see a timeline showing: "command REQUESTED → sent to MQTT → ACKED by drone → mode transitioned to GUIDED (actual state)". I know immediately if the drone obeyed or not.

**Acceptance Criteria**
- Command dialog shows timeline of events:
  1. Command requested (timestamp, operator)
  2. Sent to MQTT (MQTT publish timestamp)
  3. ACKED by drone (drone response timestamp, latency)
  4. Actual state changed (telemetry shows new mode/armed state)
- Latency badges: <500ms = green, 500ms-2s = yellow, >2s = red
- If TIMED_OUT: show "awaiting response, retry pending" with retry count
- Alert modal for CRITICAL events (command rejected due to preflight, battery critical, EKF fail)
- Breadcrumb: "DENIED (preflight: battery 5%)" if rejected upfront
- Command query endpoint: GET `/api/commands?drone_id=HW-001&limit=50` returns last 50 commands with full timeline

**Technical Tasks**
- [ ] Update command response object to include timeline:
  ```json
  {
    "cmd_id": "...",
    "drone_id": "...",
    "command": "ARM",
    "status": "ACKED",
    "timeline": [
      {"event": "REQUESTED", "timestamp": "...", "operator_id": "..."},
      {"event": "SENT_TO_MQTT", "timestamp": "..."},
      {"event": "ACKED", "timestamp": "...", "latency_ms": 250},
      {"event": "MODE_CHANGED", "timestamp": "...", "new_mode": "GUIDED"}
    ]
  }
  ```
- [ ] Add timeline state to React command modal
  - Display timeline vertically with event cards
  - Color-code latency (green/yellow/red)
  - Show retry count and pending retries
- [ ] Add alert modal for critical events
  - Triggered on COMMAND_REJECTED, BATTERY_CRITICAL, EKF_UNHEALTHY
  - Show reason and suggested action
  - Dismiss or retry button
- [ ] Implement GET `/api/commands` endpoint with filtering + pagination
  - Query `commands` and `events` tables for drone_id, filter by date range
  - Return with full timeline and retry history
- [ ] Add command history view in UI
  - Link in navbar or RightPanel: "Command History"
  - List last 20 commands with status badges (ACKED, FAILED, PENDING_RETRY)
  - Click command to expand timeline
- [ ] Write tests: 4+ scenarios (happy path with timeline, timeout+retry, preflight rejection, alert modal)

**Definition of Done**
- [ ] Command timeline shows all events with timestamps
- [ ] Latency badges color-coded correctly
- [ ] Alert modals show for critical events
- [ ] Command history endpoint returns full timeline
- [ ] UI command modal displays timeline and retry state
- [ ] pytest: 5+ test cases passing

---

### WP-08: Circuit Breaker & Graceful Degradation (W16)

**User Story:**  
As an operator, if the MQTT broker goes down or Inventory service is slow, the app doesn't freeze or show 500 errors. It shows "working with cached data" and recovers automatically when services come back.

**Acceptance Criteria**
- MQTT reconnection strategy: 1s delay, then exponential backoff (2s, 4s, 8s) up to 30s
- Circuit breaker on Inventory service: fail-fast if 3 consecutive errors; auto-retry after 30s
- When MQTT offline: UI shows "MQTT: OFFLINE (cached data)" badge in navbar
- When Inventory offline: fleet roster shows cached drone list with caveat "data may be stale"
- Command queue queued if MQTT down; auto-retry when MQTT reconnects
- No HTTP 500 errors on service unavailability; return HTTP 503 "Service Temporarily Unavailable" with fallback data

**Technical Tasks**
- [ ] Implement MQTT reconnect strategy in `services/mqtt_client.py`
  - Configure `client.reconnect_delay_set(min_delay=1, max_delay=30)`
  - Exponential backoff on each reconnection failure
  - Log reconnection attempts at INFO level
- [ ] Implement circuit breaker on Inventory service in `services/inventory_adapter.py`
  - Track last 3 request outcomes
  - If 3 failures: circuit opens, fail-fast for 30s
  - Retry after timeout
  - Log circuit state changes
- [ ] Add MQTT connection status to WebSocket message
  - Emit `mqtt_status` event with {connected: bool, last_connected_at: timestamp}
  - Frontend listens and displays badge in navbar
- [ ] Update fleet roster endpoint to fallback to cache
  - If Inventory timeout: return HTTP 200 with cached roster + caveat flag `data_source: "cache"`
  - UI shows "data may be stale" label
- [ ] Implement command queue for offline mode
  - If MQTT offline: queue command in-memory with timestamp
  - When MQTT reconnects: flush queue, retry commands
  - Persist queue to DB if memory exhausted
- [ ] Add health check endpoints
  - GET `/api/health` returns {mqtt: bool, inventory: bool, database: bool}
  - Frontend can poll and adjust UX accordingly
- [ ] Write tests: 5+ scenarios (MQTT reconnect, inventory timeout+retry, command queue, cache fallback, health check)

**Definition of Done**
- [ ] MQTT reconnects automatically with exponential backoff
- [ ] Circuit breaker opens after 3 failures; retries after 30s
- [ ] UI shows MQTT/service status badges
- [ ] Fleet roster falls back to cache if Inventory down
- [ ] Commands queued if MQTT offline; retry on reconnect
- [ ] No HTTP 500 errors on service unavailability
- [ ] pytest: 6+ test cases passing

---

### WP-09: Environment Separation (SIM vs PROD) (W16-W17)

**User Story:**  
As a fleet ops manager, I can toggle "SIM | PROD" modes in the UI. In SIM mode, I can only command simulated drones (SIM-*). In PROD mode, I only see real hardware drones (HW-*). This prevents accidental commands to real drones during testing.

**Acceptance Criteria**
- MQTT topics segregated: `fleet/sim/{drone_id}/telemetry` vs `fleet/prod/{drone_id}/telemetry`
- Backend config: `DRONE_ENV=sim | prod` at startup; server rejects commands to wrong environment
- UI environment toggle at top-right: shows current mode + allows switch (forces page reload)
- Docker Compose: separate profiles for `sim` and `prod` (hardware.yml uses `prod` by default)
- Drone roster filters by environment automatically
- Commands to wrong env rejected with HTTP 400 "Environment mismatch"

**Technical Tasks**
- [ ] Add DRONE_ENV config to FastAPI app
  - Load from env var; default to `prod`
  - Controller checks: if DRONE_ENV=prod, reject commands to SIM-* drones
- [ ] Add environment filter to telemetry handler
  - Subscribe to `fleet/+/{drone_id}/telemetry` → parse the env part
  - Ignore messages from wrong environment
- [ ] Update drone_states filtering
  - Only include drones matching current DRONE_ENV
  - GET `/api/fleet/inventory` filters by env
- [ ] Update React UI with env toggle
  - Button at top-right: "SIM | PROD" (whichever is current)
  - Click to switch: POST `/api/environment/set?env=sim` → reload page
- [ ] Update docker-compose.hardware.yml
  - Add `environment: DRONE_ENV=prod` to mission-control service
  - SwarmSim publishes to `fleet/sim/SIM-*/telemetry` (no change needed, already has SIM- prefix)
  - Add prod profile for hardware gateway (drone_gateway.py runs separately, posts to fleet/prod/HW-*)
- [ ] Write tests: 4+ scenarios (SIM env only shows SIM drones, PROD env only shows HW drones, command rejected to wrong env, env toggle works)

**Definition of Done**
- [ ] MQTT topics segregated by environment
- [ ] UI shows environment toggle and filters by current env
- [ ] Commands to wrong environment rejected (HTTP 400)
- [ ] docker-compose.hardware.yml uses DRONE_ENV=prod
- [ ] pytest: 4+ test cases passing

---

### WP-10: Load Testing + Chaos Engineering (W17)

**User Story:**  
As a platform engineer, I can simulate 50 drones sending telemetry concurrently and issue commands to multiple drones to verify the system handles production load.

**Acceptance Criteria**
- Locust load test script simulates 50 virtual drones
- Each drone sends telemetry every 1s (50 msgs/sec MQTT + 50 telemetry API calls/sec)
- 5 concurrent users (operators) issue commands every 5s during test
- System handles without queuing, errors, or UI latency >100ms (p99)
- Database throughput: 100+ events/sec without degradation
- MQTT broker handles 50+ concurrent publishers
- After 5-min test, system stable; no memory leaks

**Technical Tasks**
- [ ] Create Locust load test script `tests/load_test_locust.py`
  - SimulatedDrone class: sends telemetry with realistic lat/lon changes
  - SimulatedOperator class: issues commands (ARM, waypoint_goto) at intervals
  - Ramping profile: start with 10 drones, add 10 every 30s up to 50
  - Duration: 5 min
  - Metrics: response time, error rate, throughput
- [ ] Configure MQTT test broker to accept 50+ publishers
  - Docker Compose: mosquitto service with `max_connections=-1` (unlimited)
- [ ] Run load test and collect metrics
  - Target: <100ms p99 latency on GET `/api/fleet/inventory`
  - Target: <500ms p99 latency on POST `/api/command`
  - Target: 0% error rate on telemetry ingestion
  - DB CPU < 80%, memory stable
- [ ] Implement chaos scenarios
  - Kill MQTT broker mid-test; verify reconnection and recovery
  - Introduce 100ms random latency on DB queries; verify circuit breaker
  - Simulate packet loss on MQTT (add random message drop)
- [ ] Profile & optimize hot paths if needed
  - Use Python cProfile to identify bottlenecks
  - Optimize telemetry processing if > 500ms
  - Add caching for repeated queries

**Definition of Done**
- [ ] Locust load test runs 5 min with 50 drones
- [ ] <100ms p99 latency on all REST endpoints
- [ ] 0% error rate on telemetry
- [ ] DB stable under sustained 100+ events/sec
- [ ] Chaos scenarios tested: MQTT restart, DB latency, packet loss
- [ ] Load test report saved to `.context/reports/load_test_2026_w17.html`

---

### WP-11: Architecture Docs + Operator Runbook (W18)

**User Story:**  
As a new operator or developer, I can follow the v4 architecture guide and operator runbook to understand the system and troubleshoot common issues.

**Acceptance Criteria**
- Architecture doc covers: state machine, event sourcing, command flow, health scoring, auth model, reliability patterns
- Operator runbook covers: common scenarios (armed drone loses signal, prearm failure, mission pause/resume, multi-drone handoff)
- Migration guide: v3 → v4 data import, backward-compat layer details
- API contract document: all endpoints with request/response examples, error codes
- Database schema diagram (ER diagram) and data flow diagrams
- Deployment guide: Docker Compose setup, env vars, health checks

**Technical Tasks**
- [ ] Write Architecture Design Doc (`.context/project/V4_ARCHITECTURE.md`)
  - Sections: overview, state machine, event sourcing, command flow, health scoring, security model
  - Includes sequence diagrams (command lifecycle, multi-mission)
  - Tech stack rationale
  - Scaling considerations
- [ ] Write Operator Runbook (`.context/project/V4_OPERATOR_RUNBOOK.md`)
  - Section: "What to do when..."
    - Armed drone loses signal → check last_seen, health score, resend command if needed
    - Prearm check fails → read drone health, check battery/GPS/EKF, humanly verify issue
    - Mission paused mid-task → resume from checkpoint; drones continue from last waypoint
    - Multi-drone handoff → mission plan transferred to next operator; login with their JWT
  - Troubleshooting section: common errors and fixes
- [ ] Write Migration Guide (`.context/project/V3_V4_MIGRATION.md`)
  - How to import v3 command history (if needed)
  - Backward-compat layer for old API endpoints (optional)
  - Testing procedure for v4 with v3 drones
- [ ] Write API Contract Doc (`.context/project/V4_API_CONTRACT.md`)
  - All endpoints with OpenAPI-generated spec
  - Request/response examples for each endpoint
  - Error codes and their meanings
  - Auth headers and JWT structure
- [ ] Draw ER diagram of database schema
- [ ] Draw flow diagrams: command lifecycle, mission execution, health scoring, recovery
- [ ] Write Deployment Guide (`.context/project/V4_DEPLOYMENT.md`)
  - Docker Compose setup
  - Environment variables (all required + optional)
  - Health checks and verification
  - Backup/restore procedures

**Definition of Done**
- [ ] All 4 core docs written and proofread
- [ ] Diagrams created (ER, sequence, flow)
- [ ] Deployment guide tested on clean Docker env
- [ ] Docs linked from README
- [ ] Docs cover all v4 features

---

## Sprint Delivery Plan

| Week | Phase | Focus | Exit Criteria |
|------|-------|-------|--------------|
| W10 | 1 | DB setup (WP-01), command validator & retry (WP-02) | Schema deployed, preflight checks working, retry logic tested |
| W11 | 1 | Finish WP-02 QA, begin WP-03 | Command validator fully tested, no preflight bypass |
| W12-W13 | 2 | Multi-mission FSM (WP-03), health scoring (WP-04) | 2+ concurrent missions, health colors on roster |
| W14 | 3 | JWT auth (WP-05), start interactive builder (WP-06) | Login page functional, mission builder basic waypoints |
| W15 | 3 | Finish mission builder (WP-06), command timeline (WP-07) | Geofence + formations working, command timeline in UI |
| W16 | 4 | Circuit breaker (WP-08), env separation (WP-09) | MQTT resilience tested, SIM/PROD toggle working |
| W17 | 4 | Load testing (WP-10), chaos scenarios | 50 drones sustained, <100ms latency |
| W18 | 5 | Docs + runbook (WP-11), final QA | All docs complete, deployment guide tested |

---

## Risk Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| PostgreSQL event log grows unbounded | Medium | High | Partition by drone_id; archive old events; implement retention policy (e.g., keep 1 year) |
| LangGraph complexity unseen | Medium | High | Spike with single tool on W10 day 1; use pre-built patterns |
| Auth token refresh complexity | Low | Medium | Start with long-lived tokens (1 day); refresh token support deferred to W19 |
| Retry logic causes duplicate commands | Low | High | Idempotency keys in MQTT payloads; dedup on drone side |
| Circuit breaker too aggressive (kills traffic) | Low | Medium | Conservative thresholds (3 errors before open); auto-retry after 30s |
| Database connection pool exhaustion | Low | Medium | Configure pool size per load test; monitor connection count |
| Load test uncovers fundamental bottleneck | Medium | High | Profile early (W15); optimize hot paths in parallel |

---

## Success Criteria Checklist

> **Update as each work package completes. Keep this as single source of truth for sprint progress.**

### Global Gate

- [ ] All 61 existing tests still passing (no regressions)
- [ ] TypeScript compiles clean
- [ ] Code lints without errors
- [ ] Docker Compose starts healthy
- [ ] Manual 30-min demo script runs end-to-end cleanly

### WP-01: Database Setup

- [ ] PostgreSQL schema deployed with all tables
- [ ] Alembic migrations up/down verified
- [ ] Event append + query + snapshot + rebuild tested
- [ ] Pytest: 5+ test cases PASS
- [ ] Documentation complete

### WP-02: Command Validator & Retry

- [ ] Preflight endpoint returns correct health status
- [ ] Commands rejected if battery < 10%, EKF unhealthy, GPS < 4 sats
- [ ] Retry logic: timeout → 1s → 2s → 4s backoff
- [ ] Command DB log shows all attempts with timestamps
- [ ] Pytest: 8+ test cases PASS
- [ ] No command published to MQTT if preflight fails

### WP-03: Multi-Mission FSM

- [ ] Multiple missions can run concurrently
- [ ] Pause mission A doesn't pause mission B
- [ ] Tasks assigned and distributed to drones
- [ ] Checkpoint saved on PAUSE; restored on RESUME
- [ ] Pytest: 6+ test cases PASS
- [ ] State rebuilds from event log after restart

### WP-04: Drone Health Scoring

- [ ] Health metric calculated: min(battery, GPS, EKF, signal)
- [ ] Color-coded roster: RED < 0.3, YELLOW < 0.7, GREEN ≥ 0.7
- [ ] Alerts generated on health transitions to RED
- [ ] GET `/api/fleet/health` returns counts + details
- [ ] Pytest: 5+ test cases PASS

### WP-05: JWT Auth + RBAC

- [ ] Login page loads and authenticates with demo credentials
- [ ] OBSERVER can only view; rejected on command (HTTP 403)
- [ ] PILOT can command assigned drones only
- [ ] ADMIN can command all drones
- [ ] All events show operator_id
- [ ] Pytest: 8+ test cases PASS

### WP-06: Interactive Mission Builder

- [ ] Drag to add waypoints; click marker to delete
- [ ] Geofence polygon drawing + validation (waypoints in/out)
- [ ] Formation selector: V, LINE, CIRCLE
- [ ] Mission save persists to DB
- [ ] Mission load retrieves and displays on map
- [ ] Undo/redo works
- [ ] Component tests: 5+ scenarios PASS

### WP-07: Command Timeline UX

- [ ] Command dialog shows timeline: REQUESTED → SENT → ACKED → STATE_CHANGED
- [ ] Latency badges: <500ms (green), 500ms-2s (yellow), >2s (red)
- [ ] Retry pending shown with count
- [ ] Alert modals for critical events
- [ ] GET `/api/commands` returns history with full timeline
- [ ] Pytest: 5+ test cases PASS

### WP-08: Circuit Breaker

- [ ] MQTT reconnect: 1s → 2s → 4s → 8s → 30s (exponential)
- [ ] Inventory circuit breaker: fails fast after 3 errors, retries after 30s
- [ ] UI shows MQTT/service status badges
- [ ] Fleet roster falls back to cache if Inventory down
- [ ] Commands queued if MQTT offline; retry on reconnect
- [ ] Pytest: 6+ test cases PASS

### WP-09: Environment Separation

- [ ] MQTT topics: `fleet/sim/SIM-*/telemetry` vs `fleet/prod/HW-*/telemetry`
- [ ] Backend rejects commands to wrong environment
- [ ] UI environment toggle (SIM | PROD) filters roster
- [ ] docker-compose.hardware.yml uses DRONE_ENV=prod
- [ ] Pytest: 4+ test cases PASS

### WP-10: Load Testing

- [ ] Locust load test: 50 drones sustained
- [ ] <100ms p99 latency on GET `/api/fleet/inventory`
- [ ] <500ms p99 latency on POST `/api/command`
- [ ] 0% error rate on telemetry
- [ ] Chaos scenarios tested: MQTT restart, DB latency, packet loss
- [ ] Load test report saved

### WP-11: Docs + Runbook

- [ ] Architecture design doc complete
- [ ] Operator runbook with 5+ scenarios
- [ ] Migration guide v3 → v4
- [ ] API contract (OpenAPI spec)
- [ ] ER diagram + flow diagrams
- [ ] Deployment guide tested on clean Docker

---

## Immediate Next Actions (W10 Start)

1. **Day 1:** Create PostgreSQL schema (WP-01 task)
2. **Day 1:** Spike single-tool agent on LangGraph (if using future AI features)
3. **Day 2-3:** Implement Alembic migrations + Event model
4. **Day 3-4:** Implement preflight checker (WP-02)
5. **Day 5:** First end-to-end test: send command → preflight check → MQTT publish

---

## References

- **v3 Code:** `poc/mission_control_v3.py`, `ui/src/`
- **Existing Tests:** Count with `pytest --collect-only | grep "test_"`
- **Docker Compose:** See `ops/docker-compose.hardware.yml` (template for v4)
- **Architecture Plan:** `MISSION_CONTROL_V4_PLAN.md` (detailed spec)

