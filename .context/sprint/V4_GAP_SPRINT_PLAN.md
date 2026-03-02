# Mission Control v4 — Gap Analysis Sprint Plan

**Created:** 2026-03-02  
**Last Updated:** 2026-03-22  
**Branch Base:** `feature/04-mission-control-v4`  
**Current Status:** ~70–75% complete (W11 ✅ done, W12 ✅ done, W13 ✅ done, W14–W16 pending)  
**Reference Plan:** `d:\refrences\MISSION_CONTROL_V4_PLAN.md`  
**Reference Summary:** `d:\refrences\V4_QUICK_SUMMARY.md`

---

## Baseline: What's Already Done (W10 + W11)

| Component | Sprint | State |
|-----------|--------|-------|
| FastAPI app factory (`app.py`) | W10 | ✅ Done |
| `Settings` config with all thresholds | W10 | ✅ Done |
| `Command` + `Event` SQLAlchemy models (schema only) | W10 | ✅ Done |
| `PreflightService` — battery, GPS, EKF, calibration, sensor health | W10 | ✅ Done |
| `CommandService.submit_command()` — preflight-first rejection | W10 | ✅ Done |
| `InMemoryCommandRepository` + `InMemoryEventRepository` | W10 | ✅ Done (stub) |
| REST: `/api/health`, `/api/drones/{id}/preflight`, `/api/commands`, `/api/fleet/health` | W10 | ✅ Done (partial) |
| `ServiceContainer` / `get_service_container()` singleton | W10 | ✅ Done |
| 3 passing unit tests | W10 | ✅ Done |
| `ui/src/v4/` frontend routed shell | W10 | ✅ Done (stub) |
| PostgreSQL 16 service (docker-compose, alembic) | **W11** | **✅ DONE** |
| `Mission`/`Task`/`Drone`/`DroneSnapshot`/`Operator` ORM models | **W11** | **✅ DONE** |
| `SQLCommandRepository` + `SQLEventRepository` (DB-backed) | **W11** | **✅ DONE** |
| `DroneRepository` + `DroneSnapshotRepository` | **W11** | **✅ DONE** |
| `EventReplayService` (snapshot-based state reconstruction) | **W11** | **✅ DONE** |
| Alembic migration `2c546c1e5c55` (all 7 tables, reversible) | **W11** | **✅ DONE** |
| 21 new unit tests; total 24/24 passing | **W11** | **✅ DONE** |
| `CommandStatus.TIMED_OUT` + `CommandStatus.RETRYING` added | **W12** | **✅ DONE** |
| `get()` + `mark_retrying/acked/timed_out/failed()` on both command repos | **W12** | **✅ DONE** |
| `CommandService._retry_loop()` (threading.Thread daemon) + ACK/NACK timeout | **W12** | **✅ DONE** |
| `ack_command()` + `nack_command()` on `CommandService` | **W12** | **✅ DONE** |
| `GET /api/commands/{cmd_id}`, `POST .../ack`, `POST .../nack` endpoints | **W12** | **✅ DONE** |
| `schemas/mission.py` — `MissionStatus`, `TaskState`, request/response models | **W12** | **✅ DONE** |
| `repos/mission_repo.py` — InMemory + SQL mission repositories | **W12** | **✅ DONE** |
| `services/mission_service.py` — FSM-guarded mission lifecycle | **W12** | **✅ DONE** |
| Full mission REST API (plan/start/pause/resume/complete/abort) | **W12** | **✅ DONE** |
| `db/seed.py` — 12 SIM + 2 HW drones + 2 sample missions | **W12** | **✅ DONE** |
| `WebSocketManager` — connect/disconnect/broadcast/broadcast_sync | **W13** | **✅ DONE** |
| `HealthService` — score_drone, fleet_summary, get_drone_health | **W13** | **✅ DONE** |
| `InMemoryDroneRepository` (in-memory, mirrors DroneRepository API) | **W13** | **✅ DONE** |
| `DroneHealthResult` schema + `DRONE_HEALTH_EVENT` constant | **W13** | **✅ DONE** |
| Real `GET /api/fleet/health` (replaces placeholder) | **W13** | **✅ DONE** |
| `GET /api/drones/{id}/health` endpoint | **W13** | **✅ DONE** |
| `GET /ws` WebSocket endpoint | **W13** | **✅ DONE** |
| `CommandService` WS broadcast on every status transition | **W13** | **✅ DONE** |
| `HealthService` WS broadcast after each score update | **W13** | **✅ DONE** |
| 46 new tests (health scoring, offline, fleet API, WS manager, WS events); total 178/178 | **W13** | **✅ DONE** |

---

## Gap Summary

| # | Gap | Plan Task | Status | Resolution Sprint |
|---|-----|-----------|--------|-------------------|
| G1 | No real DB session — `InMemory*` repos only | S4-001 | ✅ RESOLVED | W11 |
| G2 | No Alembic migrations | S4-001 | ✅ RESOLVED | W11 |
| G3 | No `Mission` / `Drone` / `Operator` models | S4-001, S4-004 | ✅ RESOLVED | W11 |
| G4 | Event sourcing: no DB persistence, no snapshot | S4-002 | ✅ RESOLVED | W11 |
| G5 | Command retry loop missing (config exists, execution absent) | S4-003 | ✅ RESOLVED | W12 |
| G6 | Multi-mission state machine entirely absent | S4-004 | ✅ RESOLVED | W12 |
| G7 | `/api/fleet/health` returns zeros — health scoring not implemented | S4-005 | ✅ RESOLVED | W13 |
| G8 | No WebSocket broadcast (socket constants exist, no transport) | S4-007 | ✅ RESOLVED | W13 |
| G9 | No JWT auth — every command endpoint is open | S4-008 | P1 |
| G10 | No MQTT topic routing `fleet/{env}/{drone_id}` | S4-010 | P1 |
| G11 | No circuit breaker / MQTT reconnect backoff | S4-009 | P2 |
| G12 | Interactive mission builder (UI) absent | S4-006 | P2 |
| G13 | Integration + stress tests absent | S4-011 | P2 |
| G14 | Architecture docs + runbook absent | S4-012 | P3 |

---

## Sprint Allocation

| Sprint | Window | Theme | Gaps Addressed | Status |
|--------|--------|-------|----------------|--------|
| **W11** | 2026-03-09 — 2026-03-15 | Persistence + Event Sourcing | G1, G2, G3, G4 | ✅ DONE |
| **W12** | 2026-03-16 — 2026-03-22 | Command Retry + Mission Model | G5, G6 | ✅ DONE |
| **W13** | 2026-03-23 — 2026-03-29 | Health Scoring + Real-Time Feedback | G7, G8 | ✅ DONE |
| **W14** | 2026-03-30 — 2026-04-05 | Auth + Environment Separation | G9, G10 | pending |
| **W15** | 2026-04-06 — 2026-04-12 | Reliability + Interactive UI | G11, G12 | pending |
| **W16** | 2026-04-13 — 2026-04-19 | Integration Testing + Docs | G13, G14 | pending |

---

---

## Sprint W11: Persistence + Event Sourcing ✅ COMPLETE

**Branch:** `feature/04b-event-sourcing`  
**Gaps:** G1, G2, G3, G4  
**Plan Tasks:** S4-001, S4-002  
**Status:** ✅ **DELIVERED** (commits `77d011e` + `ff5011d`)

### Summary

✅ PostgreSQL 16 service added to docker-compose.v4.yml  
✅ DB session factory + `get_db()` FastAPI dependency  
✅ Mission/Task, Drone/DroneSnapshot, Operator ORM models  
✅ Cross-dialect types: JsonBType (JSON/JSONB), UuidType  
✅ SQLCommandRepository + SQLEventRepository (injectable factory pattern)  
✅ DroneRepository + DroneSnapshotRepository  
✅ EventReplayService: snapshot-based state reconstruction  
✅ ServiceContainer wired via `USE_DATABASE` flag  
✅ Alembic migration `2c546c1e5c55`: all 7 tables (upgrade/downgrade verified)  
✅ **24/24 tests passing** (3 W10 + 21 new)  
✅ Merged to `feature/04-mission-control-v4`  

### Original Goal (now complete)

Replaced the `InMemory*` stubs with real SQLAlchemy-backed persistence. Wired Alembic migrations. Introduced `Mission`, `Drone`, and `Operator` models. Proved the event log is append-only, queryable, and can reconstruct drone state from events.

---

### Phase Details

#### Phase W11-A: Database Infrastructure ✅ COMPLETE

~~Add SQLAlchemy async session factory + Alembic + PostgreSQL container.~~ **DONE**

**Files to create / modify:**

| File | Action | Purpose |
|------|--------|---------|
| `poc/v4_mission_control/db/session.py` | Create | Async `AsyncSession` factory via `create_async_engine` |
| `poc/v4_mission_control/db/alembic/` | Create | Alembic env + initial migration |
| `ops/docker-compose.yml` | Modify | Add `postgres` service for v4 |
| `poc/v4_mission_control/config.py` | Modify | Add `DATABASE_URL` setting |

**Implementation notes:**

```python
# poc/v4_mission_control/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

**Alembic target revision:** create tables `commands`, `events` (already modelled), plus new `missions`, `drones`, `operators`.

---

#### Phase W11-B: Missing ORM Models

Add the three missing models required by S4-001.

**Files to create:**

| File | Action | Purpose |
|------|--------|---------|
| `poc/v4_mission_control/models/mission.py` | Create | `Mission` + `Task` tables |
| `poc/v4_mission_control/models/drone.py` | Create | `Drone` registry + last-seen metadata |
| `poc/v4_mission_control/models/operator.py` | Create | `Operator` + `role` field |

**`Mission` model shape:**
```python
class Mission(TimestampMixin, Base):
    __tablename__ = "missions"
    mission_id: Mapped[str]        # "M-001"
    type: Mapped[str]              # "PATROL", "ESCORT", ...
    status: Mapped[str]            # FSM state
    config_json: Mapped[dict]      # JSONB
    created_by: Mapped[str | None]
```

**`Task` model shape:**
```python
class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    task_id: Mapped[str]
    mission_id: Mapped[str]        # FK → missions.mission_id
    drone_ids_json: Mapped[list]   # JSONB array
    type: Mapped[str]
    state: Mapped[str]
    waypoints_json: Mapped[list]
    formation: Mapped[str | None]
```

**`Drone` model shape:**
```python
class Drone(TimestampMixin, Base):
    __tablename__ = "drones"
    drone_id: Mapped[str]
    env: Mapped[str]               # "SIM" | "HARDWARE"
    last_seen_at: Mapped[datetime | None]
    last_telemetry_json: Mapped[dict]
    health_score: Mapped[float | None]
    health_label: Mapped[str | None]  # "GREEN" | "YELLOW" | "RED" | "OFFLINE"
```

**`Operator` model shape:**
```python
class Operator(TimestampMixin, Base):
    __tablename__ = "operators"
    operator_id: Mapped[str]
    username: Mapped[str]
    role: Mapped[str]              # "PILOT" | "OBSERVER" | "ADMIN"
    hashed_password: Mapped[str]
```

---

#### Phase W11-C: SQLAlchemy-Backed Repositories

Replace `InMemoryCommandRepository` and `InMemoryEventRepository` with real DB-backed versions. Keep the in-memory versions for test isolation.

**Files to modify / create:**

| File | Action |
|------|--------|
| `poc/v4_mission_control/repos/command_repo.py` | Add `SQLCommandRepository` (implements same interface) |
| `poc/v4_mission_control/repos/event_repo.py` | Add `SQLEventRepository` (append-only) |
| `poc/v4_mission_control/api/dependencies.py` | Add `get_db` FastAPI dependency; inject `SQLCommandRepository` |
| `poc/v4_mission_control/services/runtime.py` | Switch prod container to SQL repos; keep in-memory for tests |

---

#### Phase W11-D: Event Sourcing Completeness

S4-002 requires more than just an events table.

**Additions:**

| Item | Implementation |
|------|---------------|
| Snapshot table | `DroneSnapshot` model: `{drone_id, version_seq, state_json, created_at}` |
| Snapshot trigger | Write snapshot every 100 events per `drone_id` |
| State rebuild | `EventReplayService.rebuild_drone_state(drone_id)` traverses event log → applies to in-memory state |
| Event types | Enum / constants: `COMMAND_REQUESTED`, `COMMAND_ACKED`, `COMMAND_FAILED`, `COMMAND_RETRYING`, `TELEMETRY_RECEIVED`, `MISSION_CREATED`, `MISSION_STARTED`, `MISSION_PAUSED`, `MISSION_COMPLETED` |

---

### W11 Implementation Checklist ✅ ALL COMPLETE

#### Infrastructure
- [x] Add `postgresql` service to `ops/docker-compose.yml`
- [x] Add `DATABASE_URL` to `config.py` (default: `postgresql+asyncpg://v4:v4@localhost:5432/missioncontrol`)
- [x] Create `poc/v4_mission_control/db/session.py` with async engine + session factory
- [x] Run `alembic init poc/v4_mission_control/db/alembic`
- [x] Configure `alembic/env.py` to use `Base.metadata` from all models
- [x] Generate initial migration: `alembic revision --autogenerate -m "initial_v4_schema"`
- [x] Verify migration forward + rollback: `alembic upgrade head && alembic downgrade base`

#### Models
- [x] Create `poc/v4_mission_control/models/mission.py` (`Mission`, `Task`)
- [x] Create `poc/v4_mission_control/models/drone.py` (`Drone`, `DroneSnapshot`)
- [x] Create `poc/v4_mission_control/models/operator.py` (`Operator`)
- [x] Update `poc/v4_mission_control/models/__init__.py` to export all models
- [x] Confirm all models are picked up by Alembic autogenerate

#### Repositories
- [x] Add `SQLCommandRepository` to `repos/command_repo.py` (same interface as `InMemoryCommandRepository`)
- [x] Add `SQLEventRepository` to `repos/event_repo.py` (append-only; no update/delete methods)
- [x] Add `DroneSnapshotRepository` to `repos/drone_repo.py`
- [x] Update `api/dependencies.py` to inject `get_db` as a FastAPI dependency
- [x] Update `services/runtime.py`: prod `ServiceContainer` uses SQL repos; test `ServiceContainer` keeps in-memory

#### Event Sourcing
- [x] Add `EVENT_TYPES` constants module at `poc/v4_mission_control/events/types.py`
- [x] Implement `EventReplayService` with `rebuild_drone_state(drone_id: str, session: AsyncSession)`
- [x] Add `DroneSnapshot` model + snapshotting logic in `SQLEventRepository.append()` (trigger every 100 events)
- [x] Add `GET /api/events?drone_id=&aggregate_type=&limit=` endpoint
- [ ] Add seed script: `poc/v4_mission_control/db/seed.py` (10 SIM drones, 2 HW drones, sample events) — **deferred to W12**

#### Tests
- [x] `test_sql_command_repo.py` — CRUD + list_recent against in-memory SQLite (`:memory:`)
- [x] `test_sql_event_repo.py` — append-only enforcement, snapshot trigger at 100 events
- [x] `test_event_replay.py` — rebuild drone state from event stream
- [x] All 3 existing W10 tests still pass
- [x] Migration reversibility test in CI

#### DoD (S4-001 + S4-002)
- [x] `pytest poc/tests/` — all pass (24/24)
- [x] Migrations reversible: `alembic upgrade head` + `alembic downgrade base` cleanly
- [ ] Schema documented in `poc/v4_mission_control/db/SCHEMA.md` — **deferred to W16**
- [x] `EventReplayService` rebuilds state in < 1 s for 1 000 events (benchmark test)

---

---

## Sprint W12: Command Retry + Mission Model ✅ COMPLETE

**Branch:** `feature/04c-command-retry-mission-fsm`  
**Gaps:** G5, G6  
**Plan Tasks:** S4-003 (completion), S4-004  
**Status:** ✅ **DELIVERED** (commit `65d8d1e`)

### Goal

Complete the retry execution path in `CommandService`. Implement the multi-mission state machine with `Mission` + `Task` FSM and the `/api/mission/*` endpoint family.

---

### Phase Details

#### Phase W12-A: Command Retry Execution (G5)

`COMMAND_MAX_RETRIES=3` and `COMMAND_RETRY_BACKOFF_SEC=(1, 2, 4)` already exist in `Settings`. The retry loop is missing from `CommandService`.

**Required changes to `services/commands.py`:**

```python
async def _retry_loop(self, record: StoredCommand) -> None:
    """Retry a REQUESTED command up to COMMAND_MAX_RETRIES times."""
    backoffs = self._settings.COMMAND_RETRY_BACKOFF_SEC
    for attempt, delay in enumerate(backoffs, start=1):
        await asyncio.sleep(delay)
        ack = await self._await_ack(record.cmd_id, timeout=self._settings.COMMAND_ACK_TIMEOUT_SEC)
        if ack:
            self._command_repo.mark_acked(record.cmd_id)
            self._event_repo.append(event_type="COMMAND_ACKED", ...)
            return
        self._command_repo.mark_retrying(record.cmd_id, attempt=attempt)
        self._event_repo.append(event_type="COMMAND_RETRYING", ...)
    # exhausted
    self._command_repo.mark_timed_out(record.cmd_id)
    self._event_repo.append(event_type="COMMAND_TIMED_OUT", ...)
```

**Command status FSM additions:**
```
REQUESTED → RETRYING → ACKED
                     → TIMED_OUT
                     → FAILED
```

Add missing `CommandStatus` values (`RETRYING`, `TIMED_OUT`, `FAILED`) to `schemas/command.py`.

---

#### Phase W12-B: Multi-Mission State Machine (G6)

**Mission FSM:**
```
IDLE → PLANNING → PLANNED → ACTIVE ↔ PAUSED → COMPLETED
                                              → ABORTED
```

**Task FSM (per task within a mission):**
```
PLANNED → ACTIVE → COMPLETED
                 → FAILED
                 → ABORTED
```

**New service: `services/mission_service.py`**

```python
class MissionService:
    def create_mission(self, payload: MissionCreateRequest) -> Mission: ...
    def start_mission(self, mission_id: str) -> Mission: ...
    def pause_mission(self, mission_id: str) -> Mission: ...
    def resume_mission(self, mission_id: str) -> Mission: ...
    def abort_mission(self, mission_id: str) -> Mission: ...
    def get_mission(self, mission_id: str) -> Mission: ...
    def list_missions(self, status: str | None = None) -> list[Mission]: ...
    def assign_drone_to_task(self, mission_id: str, task_id: str, drone_id: str) -> Task: ...
```

**New API endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/missions` | Create a new mission |
| `GET` | `/api/missions` | List missions (filterable by status) |
| `GET` | `/api/missions/{id}` | Get mission detail + tasks |
| `POST` | `/api/missions/{id}/start` | Transition to ACTIVE |
| `POST` | `/api/missions/{id}/pause` | Transition to PAUSED |
| `POST` | `/api/missions/{id}/resume` | Resume from PAUSED |
| `POST` | `/api/missions/{id}/abort` | Force ABORTED |
| `POST` | `/api/missions/{id}/tasks/{task_id}/assign` | Assign drone to task |

---

### W12 Implementation Checklist

#### Command Retry (G5)
- [x] Add `RETRYING`, `TIMED_OUT`, `FAILED` to `CommandStatus` enum in `schemas/command.py`
- [x] Add `mark_retrying()`, `mark_acked()`, `mark_timed_out()`, `mark_failed()`, `get()` to both `InMemoryCommandRepository` and `SQLCommandRepository`
- [x] Implement sync `_retry_loop()` in `CommandService` (threading.Thread daemon, no asyncio)
- [x] Integrate `_retry_loop()` as a daemon thread from `submit_command()` (controlled by `start_retry_thread=True`)
- [x] Emit `COMMAND_RETRYING` / `COMMAND_TIMED_OUT` events to event log on each transition
- [x] `ack_command()` + `nack_command()` on `CommandService`
- [x] `GET /api/commands/{cmd_id}` — fetch single command
- [x] `POST /api/commands/{cmd_id}/ack` + `POST /api/commands/{cmd_id}/nack` endpoints

#### Mission Model (G6)
- [x] Create `schemas/mission.py`: `MissionStatus`, `TaskState`, `MissionCreateRequest`, `MissionResponse`, `TaskResponse`, `MissionTransitionRequest`, `MissionListResponse`
- [x] Create `repos/mission_repo.py`: `InMemoryMissionRepository` + `SQLMissionRepository`
- [x] Create `services/mission_service.py` with full FSM guard table enforcement
- [x] FSM guard: `_VALID_TRANSITIONS` dict — invalid transitions raise `ValueError`
- [x] Emit `MISSION_CREATED`, `MISSION_PLANNED`, `MISSION_ACTIVE`, `MISSION_PAUSED`, `MISSION_COMPLETED`, `MISSION_ABORTED` events
- [x] Add full mission endpoints to `api/routes.py` (CRUD + plan/start/pause/resume/complete/abort)
- [x] Wire `MissionService` + `MissionRepository` into `ServiceContainer` in `services/runtime.py`
- [x] Add seed script: `poc/v4_mission_control/db/seed.py` (12 SIM + 2 HW drones, 2 sample missions)

#### Tests
- [x] `test_command_retry.py` — 15 tests: retry loop fires 3×, marks TIMED_OUT; early ACK stops loop; nack marks FAILED; idempotent ACK
- [x] `test_mission_fsm.py` — 19 tests: all valid + invalid FSM transitions, concurrent missions, list/filter
- [x] `test_mission_api.py` — 18 tests: full CRUD + state transitions via TestClient, including 400 for invalid transitions

#### DoD (S4-003 completion + S4-004)
- [x] Retry fires 3× on timeout, marks TIMED_OUT, emits events
- [x] `POST /api/missions` creates mission; `POST /api/missions/{id}/start` transitions to ACTIVE
- [x] Two concurrent missions with different drone assignments do not interfere
- [x] **52 new tests, all passing (132 total, 0 new failures)**

---

---

## Sprint W13: Health Scoring + Real-Time Feedback ✅ COMPLETE

**Branch:** `feature/04d-health-scoring-websocket`  
**Gaps:** G7, G8  
**Plan Tasks:** S4-005, S4-007  
**Status:** ✅ **DELIVERED** (178/178 tests passing)

### Goal

Replace the `/api/fleet/health` zero-placeholder with a real health scoring engine. Wire WebSocket broadcast so the UI receives live command status updates.

---

### Phase Details

#### Phase W13-A: Drone Health Scoring (G7)

**Health formula (from plan):**
```python
health_score = min(battery_score, gps_score, ekf_score, signal_score)  # ∈ [0, 1]

battery_score  = battery_pct / 100.0          # 0% → 0.0, 100% → 1.0
gps_score      = min(gps_sats / 8.0, 1.0)    # 8 sats = full; 0 sats = 0.0
ekf_score      = 1.0 if ekf_ok else 0.0
signal_score   = max(0.0, 1.0 - (seconds_since_last_seen / stale_timeout))

CRITICAL  if score < 0.3   → label "RED"
WARNING   if score < 0.7   → label "YELLOW"
HEALTHY   if score ≥ 0.7   → label "GREEN"
OFFLINE   if last_seen > stale_timeout → label "OFFLINE"
```

**New service: `services/health_service.py`**

```python
class HealthService:
    def score_drone(self, drone: Drone) -> DroneHealthResult: ...
    def fleet_summary(self, drones: list[Drone]) -> FleetHealthSummary: ...
    def get_drone_health(self, drone_id: str) -> DroneHealthResult: ...
```

**New endpoints:**

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/api/fleet/health` | `FleetHealthSummary` (replace placeholder) |
| `GET` | `/api/drones/{id}/health` | `DroneHealthResult` |

---

#### Phase W13-B: WebSocket Broadcast (G8)

The `COMMAND_STATUS_EVENT` constant exists in `schemas/socket_events.py` but nothing broadcasts it.

**Required additions:**

- `WebSocketManager` in `poc/v4_mission_control/ws/manager.py` — manages active connections, supports `broadcast(event, payload)`
- `GET /ws` WebSocket endpoint in `api/routes.py`
- `CommandService` calls `ws_manager.broadcast(COMMAND_STATUS_EVENT, {...})` after each status transition
- `HealthService` broadcasts `DRONE_HEALTH_EVENT` after telemetry ingestion

**Socket event contracts:**
```json
// COMMAND_STATUS_EVENT
{
  "event": "command_status",
  "cmd_id": "...",
  "drone_id": "SIM-001",
  "status": "ACKED",
  "attempt_count": 1
}

// DRONE_HEALTH_EVENT
{
  "event": "drone_health",
  "drone_id": "SIM-001",
  "score": 0.82,
  "label": "GREEN",
  "battery_pct": 87,
  "gps_sats": 9
}
```

---

### W13 Implementation Checklist

#### Health Scoring (G7)
- [x] Create `services/health_service.py` with `score_drone()` and `fleet_summary()`
- [x] `score_drone()` computes `min(battery, gps, ekf, signal)` score per formula
- [x] `score_drone()` assigns label: `GREEN` / `YELLOW` / `RED` / `OFFLINE`
- [x] Add `DroneHealthResult` schema to `schemas/health.py`
- [x] Replace placeholder `GET /api/fleet/health` with real `HealthService.fleet_summary()` call
- [x] Add `GET /api/drones/{id}/health` endpoint
- [x] Wire `HealthService` into `ServiceContainer`
- [x] Update `Drone` model rows with `health_score` + `health_label` after each score update

#### WebSocket (G8)
- [x] Create `poc/v4_mission_control/ws/__init__.py`
- [x] Create `poc/v4_mission_control/ws/manager.py` — `WebSocketManager` with `connect()`, `disconnect()`, `broadcast()`, `broadcast_sync()`
- [x] Add `GET /ws` WebSocket route to `api/routes.py` (via `ws_router`)
- [x] Inject `ws_manager` into `CommandService`; call `broadcast_sync(COMMAND_STATUS_EVENT, ...)` on each status change
- [x] Inject `ws_manager` into `HealthService`; call `broadcast_sync(DRONE_HEALTH_EVENT, ...)` after score update
- [x] Add `DRONE_HEALTH_EVENT` constant to `schemas/socket_events.py`

#### Tests
- [x] `test_health_service.py` — score all four components; boundary tests at 0.3 and 0.7 (20 tests)
- [x] `test_health_offline.py` — drone not seen in > `STALE_TIMEOUT_SEC` → `OFFLINE` (6 tests)
- [x] `test_fleet_health_endpoint.py` — returns correct counts after inserting test drones (8 tests)
- [x] `test_ws_broadcast.py` — `WebSocketManager.broadcast()` delivers to all active connections (10 tests)
- [x] `test_command_status_ws.py` — command submission triggers WS event via `TestClient` (5 tests)

#### DoD (S4-005 + S4-007)
- [x] `GET /api/fleet/health` returns correct `healthy/warning/critical/offline` from real data
- [x] `GET /api/drones/{id}/health` returns score + label
- [x] WebSocket client receives `command_status` event after `POST /api/commands`
- [x] Drone with `battery_pct < 10` scores `< 0.3` → `RED`

---

---

## Sprint W14: Auth + Environment Separation

**Branch:** `feature/04e-auth-env-separation`  
**Gaps:** G9, G10  
**Plan Tasks:** S4-008, S4-010

### Goal

Add JWT-based authentication with role enforcement on all command endpoints. Implement SIM/PROD MQTT topic routing and backend environment guards.

---

### Phase Details

#### Phase W14-A: JWT Auth + RBAC (G9)

**Roles:**
```
OBSERVER  → read-only (GET endpoints only)
PILOT     → read + submit commands (assigned drones only)
ADMIN     → unrestricted
```

**New files:**

| File | Purpose |
|------|---------|
| `poc/v4_mission_control/auth/__init__.py` | Module init |
| `poc/v4_mission_control/auth/jwt.py` | Token encode/decode via `python-jose` |
| `poc/v4_mission_control/auth/dependencies.py` | `get_current_operator` FastAPI dependency |
| `poc/v4_mission_control/auth/acl.py` | Role-based permission checks |

**New endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/token` | Login → returns `{access_token, token_type}` |
| `GET` | `/api/auth/me` | Current operator info |

**ACL enforcement in `CommandService`:**
```python
if operator.role == "OBSERVER":
    raise PermissionError("read-only role cannot issue commands")
if operator.role == "PILOT" and drone_id not in operator.allowed_drones:
    raise PermissionError("not assigned to this drone")
```

---

#### Phase W14-B: Environment Separation (G10)

**MQTT topic schema:**
```
fleet/{env}/{drone_id}/telemetry     (env = sim | prod)
fleet/{env}/{drone_id}/command
fleet/{env}/{drone_id}/ack
```

**Backend guard:**
```python
if settings.ENVIRONMENT == "HARDWARE" and drone_id.startswith("SIM-"):
    raise ValueError("Cannot command SIM drones in HARDWARE environment")
if settings.ENVIRONMENT == "SIM" and drone_id.startswith("HW-"):
    raise ValueError("Cannot command HARDWARE drones in SIM environment")
```

**Config additions:**
```python
DRONE_ENV: str = "SIM"          # "SIM" | "HARDWARE" | "ALL"
MQTT_TOPIC_PREFIX: str = "fleet/sim"  # auto-derived from DRONE_ENV
```

---

### W14 Implementation Checklist

#### Auth (G9)
- [ ] Add `python-jose[cryptography]` + `passlib[bcrypt]` to `poc/requirements.txt`
- [ ] Create `auth/jwt.py`: `create_access_token()`, `decode_access_token()`
- [ ] Create `auth/dependencies.py`: `get_current_operator` FastAPI Depends
- [ ] Create `auth/acl.py`: `require_pilot()`, `require_admin()` decorators / guards
- [ ] Add `POST /api/auth/token` (username + password → JWT)
- [ ] Add `GET /api/auth/me` (decode token → operator info)
- [ ] Apply `get_current_operator` dependency to `POST /api/commands`
- [ ] Apply `get_current_operator` dependency to all mission write endpoints
- [ ] Store `issued_by: operator_id` on every `Command` record
- [ ] Update `GET /api/commands` to support `?issued_by=` filter
- [ ] Seed `operators` table with `admin/admin`, `pilot1/pilot1`, `observer1/observer1`

#### Environment Separation (G10)
- [ ] Add `DRONE_ENV` and `MQTT_TOPIC_PREFIX` to `config.py`
- [ ] Add environment guard to `CommandService._rejection_reason()`
- [ ] Update MQTT publish hook to use `fleet/{env}/{drone_id}/command` topic
- [ ] Update `swarmsim/swarmsim.py` to publish to `fleet/sim/SIM-*/telemetry`
- [ ] Add `GET /api/fleet/drones?env=sim|prod|all` filter to roster endpoint
- [ ] Update `ops/docker-compose.hardware.yml` to set `MC_V4_DRONE_ENV=HARDWARE`

#### Tests
- [ ] `test_auth_token.py` — login returns JWT; invalid credentials return 401
- [ ] `test_auth_acl.py` — OBSERVER cannot POST `/api/commands`; PILOT can for assigned drone
- [ ] `test_env_guard.py` — `ENVIRONMENT=HARDWARE` rejects `SIM-001` commands
- [ ] `test_env_guard.py` — `ENVIRONMENT=SIM` rejects `HW-001` commands
- [ ] `test_audit_trail.py` — command log includes `issued_by` after authenticated submission

#### DoD (S4-008 + S4-010)
- [ ] Unauthenticated `POST /api/commands` returns 401
- [ ] OBSERVER token receives 403 on command submission
- [ ] PILOT token succeeds on assigned drone; 403 on unassigned drone
- [ ] HARDWARE environment rejects SIM-* drone commands

---

---

## Sprint W15: Reliability + Interactive UI

**Branch:** `feature/04f-reliability-ui`  
**Gaps:** G11, G12  
**Plan Tasks:** S4-009, S4-006

### Goal

Add MQTT reconnect backoff and circuit breaker for the Inventory service. Begin interactive mission builder in the React v4 UI shell.

---

### Phase Details

#### Phase W15-A: Circuit Breaker + Graceful Degradation (G11)

**MQTT reconnect backoff:**
```python
BACKOFF_SCHEDULE = [1, 5, 30]  # seconds

async def _reconnect_with_backoff(self):
    for delay in itertools.cycle(BACKOFF_SCHEDULE):
        try:
            await self._client.connect(...)
            return
        except Exception:
            await asyncio.sleep(delay)
```

**Inventory circuit breaker (3-strike fail-fast):**
```python
class CircuitBreaker:
    def __init__(self, threshold=3, reset_timeout=30): ...
    async def call(self, fn: Callable) -> Any:
        if self.state == "OPEN":
            raise CircuitOpenError("inventory unavailable; serving cached data")
        try:
            result = await fn()
            self._reset()
            return result
        except Exception:
            self._record_failure()
            ...
```

**UI status badge:** WebSocket broadcasts `SERVICE_STATUS_EVENT` with `mqtt_connected: bool`, `inventory_available: bool`.

---

#### Phase W15-B: Interactive Mission Builder UI (G12)

**React components to implement (`ui/src/v4/`):**

| Component | Purpose |
|-----------|---------|
| `MissionBuilderMap.jsx` | Leaflet map with click-to-add-waypoint |
| `WaypointList.jsx` | Ordered list of waypoints; drag-to-reorder |
| `GeofenceEditor.jsx` | Polygon draw overlay |
| `FormationSelector.jsx` | V / Line / Circle formation picker |
| `MissionBuilderPage.jsx` | Assembled builder with submit to `POST /api/missions` |

**Map interaction:**
- Click on map → `addWaypoint({lat, lng, alt_m: 30})`
- Drag waypoint marker → updates lat/lng in state
- Click waypoint in list → centers map
- "Submit Mission" → serialises to `MissionCreateRequest` → `POST /api/missions`

---

### W15 Implementation Checklist

#### Circuit Breaker (G11)
- [ ] Create `poc/v4_mission_control/infra/mqtt_client.py` with reconnect backoff
- [ ] Create `poc/v4_mission_control/infra/circuit_breaker.py` with 3-strike fail-fast
- [ ] Wrap Inventory HTTP calls in `CircuitBreaker`
- [ ] Add `SERVICE_STATUS_EVENT` to `schemas/socket_events.py`
- [ ] Broadcast `SERVICE_STATUS_EVENT` on MQTT connect/disconnect
- [ ] Update `GET /api/health` to include `mqtt_connected` and `inventory_available` fields
- [ ] Serve `last_known_drone_states` from DB cache when real-time unavailable

#### Interactive UI (G12)
- [ ] Install `leaflet` + `react-leaflet` in `ui/`
- [ ] Create `MissionBuilderMap.jsx` with click-to-add-waypoint
- [ ] Create `WaypointList.jsx` with reorder + delete
- [ ] Create `GeofenceEditor.jsx` (polygon draw)
- [ ] Create `FormationSelector.jsx` (V / Line / Circle enum)
- [ ] Create `MissionBuilderPage.jsx` assembling all components
- [ ] Wire `MissionBuilderPage` into `ui/src/v4/routes.jsx`
- [ ] On submit: validate waypoints inside geofence; POST to `/api/missions`
- [ ] Show success/error toast on submission result

#### Tests
- [ ] `test_circuit_breaker.py` — 3 failures → OPEN; request after reset_timeout → HALF-OPEN
- [ ] `test_mqtt_reconnect.py` — mock broker down; verify backoff schedule fires
- [ ] Playwright/React Testing Library: `MissionBuilderMap` renders; click adds waypoint to list
- [ ] `test_mission_builder_submit.py` — form submit POSTs correct payload

#### DoD (S4-009 + S4-006)
- [ ] MQTT broker crash → UI shows "MQTT: OFFLINE (cached)" badge; backend continues serving cached state
- [ ] Inventory 3 failures → circuit opens; `/api/fleet` returns cached data with warning
- [ ] Can create + save a PATROL mission with 5 waypoints from UI
- [ ] Waypoint outside geofence shows validation error before submit

---

---

## Sprint W16: Integration Testing + Documentation

**Branch:** `feature/04g-testing-docs`  
**Gaps:** G13, G14  
**Plan Tasks:** S4-011, S4-012

### Goal

Stress-test the full v4 stack at 50-drone load. Validate chaos scenarios (MQTT restart, DB failover). Produce architecture docs and operator runbook.

---

### W16 Implementation Checklist

#### Integration + Stress Tests (G13)
- [ ] Install `locust` in `poc/requirements.txt`
- [ ] Create `poc/tests/load/locustfile.py` simulating 50 drones sending telemetry + commands
- [ ] Load test target: sustained 100 events/sec, < 100 ms UI latency (p99)
- [ ] Chaos test: MQTT broker restart mid-mission → verify reconnect + mission resume
- [ ] Chaos test: DB failover (stop + restart postgres container) → no data loss
- [ ] Regression: all v3 endpoints (roster, basic commands) still pass against v3 app
- [ ] Run full `pytest poc/tests/` — zero failures

#### Documentation (G14)
- [ ] Create `.context/project/V4_DESIGN_DOC.md` — state machine, event sourcing, API contracts, DB schema
- [ ] Create `.context/project/V4_MIGRATION_GUIDE.md` — v3 → v4 backward-compat layer
- [ ] Create `.context/project/V4_OPERATOR_RUNBOOK.md` — ARM fail, prearm errors, mission pause, lost signal scenarios
- [ ] Update `poc/v4_mission_control/README.md` with local dev setup (docker-compose up + pytest)

#### DoD (S4-011 + S4-012)
- [ ] Locust report: 50 drones, 5 concurrent missions, < 100 ms p99 latency
- [ ] Chaos tests pass (MQTT + DB recovery)
- [ ] New operator can connect real drone + run PATROL mission following runbook in < 30 min
- [ ] All success metrics from plan satisfied (see below)

---

---

## Overall Success Metrics (from Plan)

| Metric | Target |
|--------|--------|
| Hardware safety | 100% of command paths have preflight check |
| Persistence | 0 lost commands; 100% queryable history |
| Multi-mission | 5 concurrent drones, different roles, no cross-talk |
| UI health | < 100 ms update latency (p99) at 50 drones |
| Reliability | Graceful degradation if MQTT or DB unavailable |
| Auth | Audit trail includes `operator_id` for every command |
| Test/Prod separation | One environment toggle → fully isolated command paths |

---

## Branch Strategy

```
develop  (protected)
  │
  ├─ feature/04-mission-control-v4-backup  ← safety checkpoint (never touched)
  │                                           (created 2026-03-02 from b719158)
  │
  └─ feature/04-mission-control-v4  ← integration target
      ├─ feature/04b-event-sourcing               (W11) ──┐
      ├─ feature/04c-command-retry-mission-fsm    (W12)   ├─ PR → 04-mission-control-v4
      ├─ feature/04d-health-scoring-websocket     (W13)   ├─ (one sprint at a time)
      ├─ feature/04e-auth-env-separation          (W14)   ├─
      ├─ feature/04f-reliability-ui               (W15)   ├─
      └─ feature/04g-testing-docs                 (W16) ──┘
```

### Safety Flow

1. **Per-sprint:** Each feature branch (04b, 04c, etc.) opens a PR against `feature/04-mission-control-v4`
2. **Review & merge:** After DoD validation, merge the feature branch into `feature/04-mission-control-v4`
3. **Recovery option:** If integration breaks, reset: `git reset --hard feature/04-mission-control-v4-backup`
4. **End of epic:** When W16 is complete, final PR: `feature/04-mission-control-v4` → `develop`
5. **Cleanup:** Delete `feature/04-mission-control-v4-backup` after successful merge to `develop`

### Why This Works

- ✅ `feature/04-mission-control-v4` stays as integration target (no complexity)
- ✅ Backup branch is a single-point checkpoint (instant recovery if needed)
- ✅ No extra merge flow; sub-features PR directly to 04-mission-control-v4
- ✅ Very simple: all 6 sprints use the same pattern
