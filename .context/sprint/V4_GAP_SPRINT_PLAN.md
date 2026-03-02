# Mission Control v4 Gap Sprint Plan (W11–W16)

**Status as of 2026-03-02:** W11 complete (persistence + event sourcing). W12–W16 pending.

**Current Baseline:** ~25–30% implementation complete (W10 + W11).  
**Target:** Phase 1 completion by end of W16 (~70% → ready for Phase 2 integration testing).

---

## W11: Persistence + Event Sourcing Foundation ✅ COMPLETE

**Commits:** `77d011e` (implementation) + `ff5011d` (migration + replay fix)  
**Test Status:** 24/24 passing

**Deliverables:**
- PostgreSQL 16 service in docker-compose.v4.yml
- DB session factory + `get_db()` FastAPI dependency
- ORM models: `Mission`/`Task`, `Drone`/`DroneSnapshot`, `Operator`
- Cross-dialect types: `JsonBType` (JSON/JSONB), `UuidType`
- `SQLCommandRepository` + `SQLEventRepository` (injectable factory pattern)
- `DroneRepository` + `DroneSnapshotRepository`
- `EventReplayService`: snapshot-based state reconstruction
- `ServiceContainer` wired via `USE_DATABASE` flag
- Alembic migration `2c546c1e5c55`: all 7 tables (upgrade/downgrade verified)

**Carry-forward:** `USE_DATABASE=False` → InMemory repos (tests); `True` → SQL repos (docker)

---

## W12: Mission Planning & Task Execution Bridge

**Gap:** Mission/Task CRUD and lifecycle handoff to command execution.

**Objectives:**
1. **Mission CRUD endpoints** (`POST /missions`, `GET /missions/{id}`, `GET /missions`, `PATCH /missions/{id}/status`)
2. **Task CRUD endpoints** (`POST /missions/{id}/tasks`, `PATCH /missions/{id}/tasks/{task_id}/status`)
3. **Mission lifecycle service** — orchestrate task transitions: `PENDING` → `ASSIGNED` → `RUNNING` → `COMPLETED` | `FAILED`
4. **Command factory from Task** — auto-generate safe `Arm`, `Takeoff`, `Goto`, `Land`, `Disarm` commands from task spec
5. **Task-to-command correlation** — persist `task_id` FK in commands; link command events back to originating task
6. **Tests:** 15–20 new unit tests (CRUD, state machine, command factory, correlation)

**Acceptance Criteria:**
- [ ] POST `/missions` creates mission + child tasks; returns 201 with mission_id
- [ ] PATCH `/missions/{id}/status` to `RUNNING` auto-transitions all tasks to `ASSIGNED`
- [ ] Task executor picks `ASSIGNED` task, calls command factory, atomically writes command + task update
- [ ] Command events include original task_id; replay service re-links to task
- [ ] All new tests pass; no regression in W11 tests
- [ ] Sprint doc updated with proof links

---

## W13: Preflight Expansion & Safety Interlocks

**Gap:** Expand rigid stub preflight to multi-drone health aggregation + mission-level safety checks.

**Objectives:**
1. **Multi-drone health rollup** (`GET /preflight?drones=SIM-001,SIM-002,SIM-003`)
   - Query `Drone.health_label` for each drone
   - Aggregate: if any OFFLINE/RED → preflight `UNSAFE`; if all GREEN → `SAFE`; if mixed YELLOW → `CAUTION`
2. **Mission-scoped preflight** (`GET /missions/{id}/preflight`)
   - Retrieve mission task list
   - Extract drone_ids from task specs
   - Run health rollup on those drones
   - Add mission-level checks: `task_count > 0`, no circular task dependencies, all drones are registered
3. **Preflight event logging** — emit `PREFLIGHT_PASSED` / `PREFLIGHT_FAILED` event for audit trail
4. **ARM safety gate** — reject `ARM` command if preflight was never run or is UNSAFE
5. **Tests:** 12–15 unit tests (health rollup, mission scoped checks, event logging, ARM gate)

**Acceptance Criteria:**
- [ ] Multi-drone health endpoint aggregates correctly; tested with 3+ drones (GREEN/YELLOW/RED/OFFLINE mix)
- [ ] Mission preflight queries tasks, extracts drones, runs health rollup
- [ ] Preflight events are logged to Event table
- [ ] ARM is rejected with HTTP 409 Conflict if no preflight or UNSAFE
- [ ] All tests pass; no regression

---

## W14: Telemetry Ingestion & State Sync

**Gap:** Ingest real/simulated telemetry streams; keep `Drone` model + event log in sync.

**Objectives:**
1. **Telemetry ingestion endpoint** (`POST /telemetry`, accept batch array of `{drone_id, gps, battery, heading, ...}`)
2. **Upsert Drone row** — `DroneRepository.upsert(drone_id, last_telemetry_json, ...)`
3. **TELEMETRY_RECEIVED event** — append to event log with payload
4. **Event replay integration** — telemetry recovery via snapshot + replayed events
5. **Timestamp handling** — prefer telemetry `ts` over ingest time; reject out-of-order by >30s
6. **Simulator adapter** — update `fleet_simulator.py` to send telemetry to v4 endpoint (not just v3 MQTT)
7. **Tests:** 10–12 unit tests (upsert, event append, timestamp validation, out-of-order rejection, replay from telemetry)

**Acceptance Criteria:**
- [ ] POST `/telemetry` accepts batch; upserts drones; logs events
- [ ] Drones are queryable via `GET /drones`, `GET /drones/{id}`
- [ ] Event replay correctly rebuilds telemetry state from snapshots + events
- [ ] Out-of-order telemetry (>30s skew) is logged as warning and rejected
- [ ] Simulator adapter sends to v4 endpoint
- [ ] All tests pass

---

## W15: Command Execution & Feedback Loop

**Gap:** Close loop from command issuance → ACK/NACK/async result → event log → state.

**Objectives:**
1. **Command timeout handler** — if command not ACK'd within `COMMAND_TIMEOUT = 10s`, emit `COMMAND_TIMED_OUT` event
2. **Async result polling** (`GET /commands/{id}`)
   - Return status: `REQUESTED` → `ACKED` → pending; or `REJECTED` / `FAILED` / `TIMED_OUT`
   - Clients (simulator, real autopilot) poll this endpoint
3. **Command ACK/NACK endpoints** (`POST /commands/{id}/ack`, `POST /commands/{id}/nack`)
   - Receives feedback from external executor (simulator or ArduPilot gateway)
   - Atomically append ACK/NACK event + update command row
4. **Retry logic** — if ACK not received and command is retryable (`TAKEOFF`, `GOTO`, `LAND`), auto-retry up to 2 times with exponential backoff
5. **Command history** — GET `/commands?drone_id=SIM-001&limit=20` lists recent commands with status
6. **Tests:** 15–18 unit tests (timeouts, ACK/NACK, retries, history, state transitions)

**Acceptance Criteria:**
- [ ] Command times out correctly at 10s; `COMMAND_TIMED_OUT` event logged
- [ ] GET `/commands/{id}` returns current status JSON
- [ ] POST `/commands/{id}/ack` and `/nack` update state + log events
- [ ] Retryable commands retry automatically; max 2 retries
- [ ] Command history is queryable; sorted newest-first
- [ ] All tests pass

---

## W16: Mission Completion & Report Generation

**Gap:** Detect mission completion, aggregate final state, generate summary for review.

**Objectives:**
1. **Mission completion detector** — monitor all tasks in mission; if all `COMPLETED` or any `FAILED`, set mission to `COMPLETED` / `ABORTED`
2. **Mission report generation**
   - Collect all tasks for mission
   - Fetch all commands/events linked to tasks
   - Aggregate telemetry snapshots per drone during mission window
   - Count successes, failures, retries, timeouts
   - Compute mission duration, total distance, battery utilization
3. **Report endpoint** (`GET /missions/{id}/report`)
   - Return JSON summary: `{mission_id, status, task_results: [{id, status, command_count, events: [...]}], flight_stats: {...}}`
4. **Report event emission** — emit `MISSION_COMPLETED` or `MISSION_ABORTED` event when mission finalizes
5. **Optional: PDF/CSV export** (defer if time-constrained)
6. **Tests:** 10–12 unit tests (completion detection, report aggregation, event emission, edge cases)

**Acceptance Criteria:**
- [ ] Mission auto-completes when all tasks finish (any path via complete/abort)
- [ ] Report aggregates tasks + commands + telemetry correctly
- [ ] Report endpoint returns JSON with all required fields
- [ ] Mission completion events are logged
- [ ] All tests pass
- [ ] Manual smoke test: create 2-task mission, run end-to-end, fetch report

---

## Summary: Gaps Resolved by W16

| Gap # | Category | W11 | W12 | W13 | W14 | W15 | W16 |
|-------|----------|-----|-----|-----|-----|-----|-----|
| 1 | Persistence (DB + ORM) | ✅ | — | — | — | — | — |
| 2 | Mission/Task CRUD | — | ✅ | — | — | — | — |
| 3 | Task execution bridge | — | ✅ | — | — | — | — |
| 4 | Multi-drone health rollup | — | — | ✅ | — | — | — |
| 5 | Mission-scoped preflight | — | — | ✅ | — | — | — |
| 6 | Telemetry ingestion | — | — | — | ✅ | — | — |
| 7 | Drone state sync | — | — | — | ✅ | — | — |
| 8 | Command timeout + retry | — | — | — | — | ✅ | — |
| 9 | Async command feedback | — | — | — | — | ✅ | — |
| 10 | Command history query | — | — | — | — | ✅ | — |
| 11 | Mission completion detector | — | — | — | — | — | ✅ |
| 12 | Report aggregation | — | — | — | — | — | ✅ |
| 13 | Event audit trail | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| 14 | Test coverage (100+ new) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Branch & PR Strategy

**Integration Branch:** `feature/04-mission-control-v4`  
**Sub-features per sprint:**
- `feature/04c-missions-tasks` (W12)
- `feature/04d-preflight-expansion` (W13)
- `feature/04e-telemetry-sync` (W14)
- `feature/04f-command-feedback` (W15)
- `feature/04g-mission-completion` (W16)

**Merge Pattern:** Merge each sub-feature branch → `feature/04-mission-control-v4` (no PR required if CODEOWNER is committer), then final PR from `feature/04-mission-control-v4` → `develop` at end of W16 with full evidence mapping.

---

## Test Targets

Phase 1 completion requires:
- **Unit tests:** 120+ (24 existing W11, 15 W12, 12 W13, 10 W14, 15 W15, 10 W16) = **86 new**
- **All tests passing:** No regressions allowed
- **Test coverage:** Minimum 75% on service/repo/domain code
- **Manual smoke tests:** End-to-end mission create → execute → report (W16)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Timestamp collision in event replay (W11 carryover) | ✅ Fixed: use `version_seq` offset instead of timestamp comparison |
| Command timeout race condition | Implement idempotent ACK handler; deduplicate by command_id |
| Mission state machine deadlock | Model as acyclic DAG; add explicit transition validation |
| Telemetry backpressure | Implement queue with max size 10K; drop oldest if full |
| Report aggregation timeout | Cache report for 5min; lazy-compute on first request |

---

## Success Metrics (by end of W16)

- ✅ All 86 new tests passing
- ✅ Zero regressions in W10-W11 tests
- ✅ End-to-end mission execution (3+ drones, 5+ tasks, 10+ commands)
- ✅ Mission report generation with correct aggregation
- ✅ Benchmark: <100ms response time for preflight; <500ms for report on 10K events
- ✅ All code committed to `feature/04-mission-control-v4`

---

## Next Steps (W12 Kickoff)

1. Create Story: "Mission Planning & Task Execution Bridge" (link to this plan)
2. Create branch: `feature/04c-missions-tasks`
3. Implement Mission/Task CRUD + lifecycle orchestration
4. Open PR with evidence mapping: CRUD tests + lifecycle tests + command factory tests

