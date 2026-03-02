# Mission Control v4 Architecture

**Document Type:** Architecture Source of Truth  
**Status:** Active  
**Last Updated:** 2026-03-01  
**Companion Doc:** `V4_INTERFACE_STORYBOARD.md`

---

## Purpose

This document defines the intended v4 system architecture.

It replaces fragmented sprint planning as the architecture reference and aligns the platform to current priorities:

- Functional capability first
- Hardware safety first
- Clear v3 to v4 migration path
- Production-oriented structure, without claiming full production hardening yet

This file and `V4_INTERFACE_STORYBOARD.md` are the only v4 source-of-truth docs.

---

## Current Position

### v4 status

- v4 is in active development
- v4 is intended to become production-ready
- v4 is not yet a fully production-hardened platform

### What that means

- Safety, persistence, and structure belong in the first slices
- Full auth hardening, admin workflows, and scale-out concerns can follow after functional stability
- Auth is not "just bolt-on" forever, but it can be sequenced after the initial functional architecture if the interfaces are designed for it now

### Correct framing

Use this wording in docs and discussions:

`v4 is a development-track architecture aimed at production readiness. Initial delivery prioritizes safe functional workflows, persistence, and deployment separation. Full auth hardening and advanced admin capabilities follow in later hardening phases.`

---

## Non-Negotiable Design Decisions

### 1. Safety values are centralized

All command validation, health scoring, and UI displays must use one shared config.

### 2. Environment is deployment-scoped

The running backend is either simulator-oriented or hardware-oriented. Operators do not flip the backend between modes from the UI.

### 3. v4 should be developed side-by-side with v3

Avoid destabilizing the current v3 flow while v4 APIs and UI contracts are still moving.

### 4. Multi-mission is a deferred functional capability

The data model can remain future-ready, but the first functional slice should be single-mission active execution.

### 5. Router migration is required

The v4 UI assumes a routed application shell. That must be built before feature-heavy page work.

---

## Recommended Code Layout

To keep v3 stable, use a side-by-side v4 layout.

### Backend recommendation

```text
poc/
  mission_control_v3.py
  v4_mission_control/
    app.py
    api/
    services/
    models/
    repos/
    schemas/
    config.py
```

### Frontend recommendation

```text
ui/src/
  App.jsx                 # existing v3 shell
  v4/
    AppShell.jsx
    routes.jsx
    pages/
    components/
    stores/
```

### Why this is the safest path

- It reduces accidental breakage in the current v3 path
- It allows contract-first v4 development
- It makes rollback trivial
- It supports gradual adoption instead of a hard overwrite

This is the preferred answer to the SIM vs HARDWARE and v3 vs v4 conflict question: do not fork by runtime toggle first, fork by implementation boundary and deployment boundary.

---

## High-Level Architecture

```text
+-------------------------------------------------------------------+
|                           Mission Control v4                      |
+-------------------------------------------------------------------+
| React UI (v4 routed app)                                          |
| - dashboard                                                        |
| - missions                                                         |
| - fleet                                                            |
| - commands                                                         |
| - settings                                                         |
+-----------------------------+-------------------------------------+
| Socket.IO stream            | REST API                            |
| live updates, alerts        | commands, history, planning         |
+-----------------------------+-------------------------------------+
| FastAPI backend                                                   |
| - command validation                                              |
| - mission services                                                |
| - fleet health services                                           |
| - persistence and audit                                           |
| - auth hooks (pluggable, phased)                                  |
+------------------+-------------------+----------------------------+
| MQTT integration | PostgreSQL        | External inventory         |
| telemetry/acks   | events/state      | roster/enrichment          |
+------------------+-------------------+----------------------------+
```

---

## Core Runtime Components

### UI layer

- React + Vite
- React Router for route structure
- Zustand for client state
- Socket.IO client for live stream

### API layer

- FastAPI
- REST for explicit operations and history
- Socket.IO compatible event stream for existing client ergonomics

### Messaging layer

- MQTT remains the drone-facing transport
- Commands publish to drone-specific topics
- Telemetry and acknowledgements remain event-driven

### Persistence layer

- PostgreSQL is the primary persistent store
- SQLAlchemy + Alembic for schema and migrations

---

## Safety Configuration

All safety rules below are normalized and must stay consistent in backend, UI, tests, and ops docs.

### Default thresholds

| Key | Default | Meaning |
|-----|---------|---------|
| `BATTERY_ARM_MIN_PCT` | `10` | Minimum battery to allow ARM |
| `GPS_ARM_MIN_SATS` | `4` | Minimum satellites to allow ARM |
| `STALE_TIMEOUT_SEC` | `30` | Drone is stale/offline beyond this |
| `COMMAND_ACK_TIMEOUT_SEC` | `5` | Timeout for one command attempt |
| `COMMAND_MAX_RETRIES` | `3` | Maximum retries after first attempt |

### Retry policy

- Attempt 1: send immediately
- Retry 1: after 1 second
- Retry 2: after 2 seconds
- Retry 3: after 4 seconds
- After final failure: mark command `FAILED`

### ARM gating

Block `ARM` when any of the following is true:

- battery percentage is below 10
- visible satellites are below 4
- EKF is unhealthy
- drone is already armed
- `prearm_ok` is false
- `calibration_required` is true

### Queue replay rule

If a command was queued due to transport outage:

- do not execute it blindly on reconnect
- re-run preflight validation
- reject if expired or no longer safe
- require re-confirmation for dangerous verbs if the command is stale

This closes the unsafe "replay stale commands later" gap.

---

## Calibration and PreArm Readiness

Calibration is required for real hardware, but it is not a primary W10 operator workflow inside Mission Control.

### Operating model

- `SIM` drones are treated as calibrated by default
- `HARDWARE` drones must expose calibration and prearm readiness through telemetry or the hardware bridge
- Mission Control consumes readiness state and blocks unsafe commands
- The actual calibration procedure remains a maintenance / commissioning task outside the main mission-control flow

### What v4 owns in W10

- detect calibration-related readiness failures
- surface them in preflight responses and UI
- reject `ARM` when calibration or prearm state is not safe

### What v4 does not own in W10

- full accelerometer calibration workflow
- compass dance / live calibration UX
- gyro leveling workflow
- hardware maintenance wizard

### Required preflight fields

These fields are required in the v4 preflight contract for hardware-aware readiness:

- `prearm_ok: bool`
- `calibration_required: bool`
- `prearm_failures: string[]`
- `sensor_health: { gyro_ok, accel_ok, compass_ok, ekf_ok }`
- `last_calibrated_at: string | null` (optional in W10 storage, but valid in the contract)

### ARM rejection rule

If any of these are true, `ARM` must be rejected:

- `prearm_ok == false`
- `calibration_required == true`
- `prearm_failures` is non-empty
- any required sensor health flag is false

### Typical failure examples

- `PreArm: Gyros not calibrated`
- `PreArm: Compass not calibrated`
- `PreArm: Accel calibration required`
- `PreArm: Hardware safety switch`

This keeps calibration in the correct place: hardware setup owns calibration, Mission Control owns readiness enforcement.

---

## Health Model

### Health score

`health_score = min(battery_score, gps_score, ekf_score, signal_score)`

### Status mapping

- `GREEN`: `>= 0.70`
- `YELLOW`: `>= 0.30 and < 0.70`
- `RED`: `< 0.30`
- `OFFLINE`: telemetry stale beyond timeout

### Inputs

- Battery
- GPS satellites
- EKF health flag
- Signal freshness from last telemetry timestamp

The UI and backend must use the same labels and threshold bands.

---

## Environment Separation

### Existing operational reality

- `ops/docker-compose.yml` is the simulator-first stack
- `ops/docker-compose.hardware.yml` is the hardware integration stack

That means the architecture should not treat environment as a user toggle.

### Required model

- Environment is determined by deployment configuration
- Backend boots in one environment context
- UI shows that context
- UI may filter visible sources, but it must not mutate backend operating mode at runtime

### Recommended naming

Use:

- `SIM`
- `HARDWARE`

Avoid mixing:

- `SIM`
- `PROD`
- `LAB`

unless there is a real third deployment profile.

### Topic strategy

Two acceptable implementations exist:

#### Option A: Prefix topics by environment

- `fleet/sim/{drone_id}/telemetry`
- `fleet/hardware/{drone_id}/telemetry`
- `fleet/sim/{drone_id}/command`
- `fleet/hardware/{drone_id}/command`

#### Option B: Keep current topic shape and isolate by deployment

- `fleet/{drone_id}/telemetry`
- `fleet/{drone_id}/command`
- separate broker / service deployment per environment

### Recommendation

For immediate v4 delivery, prefer **Option B first**:

- It matches the current repo and current publishers
- It avoids forcing simultaneous topic changes in simulator, inventory, and backend
- It aligns naturally with separate compose stacks

If later needed, migrate to Option A as a controlled follow-up.

This is the pragmatic sequence:

1. Separate deployments first
2. Add explicit backend environment label
3. Add topic namespacing only when all publishers/consumers are ready

---

## Real-Time Stack Decision

There was a mismatch between `WebSocket + Redis Pub/Sub` and `WebSocket + Socket.IO`.

### Option 1: Socket.IO only

**Pros**

- Matches current client/server patterns
- Lower migration cost
- Easier incremental upgrade from current code
- Handles reconnects and event semantics simply

**Cons**

- Less ideal for horizontal fan-out at larger scale
- Shared state across multiple app instances needs extra work later

### Option 2: WebSocket + Redis Pub/Sub backbone

**Pros**

- Better scale-out story
- Easier multi-instance event fan-out
- Cleaner path to distributed workers and separate broadcasters

**Cons**

- More moving parts now
- More operational overhead
- Higher migration complexity
- Premature for current functional priority

### Recommendation

Use **Socket.IO now**, with clean abstraction around event broadcasting.

That gives:

- fastest path from v3
- least rewrite risk
- enough capability for the current development phase

Later, if horizontal scaling becomes real, add Redis behind the broadcast layer instead of forcing it into the first implementation.

---

## API and Event Responsibilities

### REST endpoints own

- command submission
- mission create and load
- command history
- fleet health queries
- threshold reads and updates
- future auth flows

### Socket stream owns

- telemetry updates
- command lifecycle updates
- alerts
- mission state changes
- service health badges

### MQTT owns

- drone commands
- telemetry ingress
- command acknowledgements

This separation keeps the contract simple.

---

## Config Loading Pattern

v4 `config.py` must use a single environment-backed settings object, not scattered module literals.

### Required pattern

- Use a `Settings` model in `config.py`
- Use Pydantic settings loading (`BaseSettings` / `pydantic-settings`)
- Export one cached `get_settings()` accessor
- Keep the five normalized threshold names as fields on `Settings`

### Required W10 fields

- `BATTERY_ARM_MIN_PCT`
- `GPS_ARM_MIN_SATS`
- `STALE_TIMEOUT_SEC`
- `COMMAND_ACK_TIMEOUT_SEC`
- `COMMAND_MAX_RETRIES`

### Implementation rule

- Backend services read config through `get_settings()`
- Tests override settings through env vars or dependency override
- Frontend uses the documented defaults until a config endpoint is added; it must not invent different values

---

## Initial REST Contract

These are the minimum canonical REST contracts for W10.

### `GET /api/health`

**Purpose**

- liveness/readiness placeholder for v4 bootstrap

**Response 200**

```json
{
  "status": "ok",
  "service": "mission-control-v4",
  "environment": "SIM",
  "timestamp": "2026-03-01T12:00:00Z"
}
```

### `POST /api/commands`

**Purpose**

- submit a single drone command through the safe command path

**Request body**

```json
{
  "drone_id": "HW-001",
  "command": "ARM",
  "params": {},
  "client_request_id": "optional-client-id",
  "requested_by": "optional-until-auth"
}
```

**Validation rules**

- `drone_id` is required
- `command` is required
- `params` defaults to `{}` if omitted
- `client_request_id` is optional and used for idempotency/correlation
- `requested_by` is optional in W10 and becomes auth-backed later

**Response 202**

```json
{
  "cmd_id": "6f2d6b95-b21a-4d2c-8c67-b9a1687bbcb1",
  "accepted": true,
  "status": "REQUESTED",
  "drone_id": "HW-001",
  "command": "ARM",
  "attempt_count": 0,
  "rejection_reason": null,
  "created_at": "2026-03-01T12:00:00Z"
}
```

**Response 400**

```json
{
  "accepted": false,
  "status": "REJECTED",
  "drone_id": "HW-001",
  "command": "ARM",
  "rejection_reason": "battery below minimum threshold"
}
```

### `GET /api/drones/{drone_id}/preflight`

**Purpose**

- return the current command-readiness and calibration-aware preflight state for one drone

**Response 200**

```json
{
  "drone_id": "HW-001",
  "prearm_ok": false,
  "calibration_required": true,
  "battery_pct": 8,
  "gps_sats": 3,
  "armed": false,
  "mode": "STANDBY",
  "prearm_failures": [
    "PreArm: Gyros not calibrated"
  ],
  "sensor_health": {
    "gyro_ok": false,
    "accel_ok": true,
    "compass_ok": true,
    "ekf_ok": true
  },
  "last_calibrated_at": null,
  "timestamp": "2026-03-01T12:00:00Z"
}
```

### `GET /api/commands`

**Purpose**

- read recent command history for the command page and debugging

**Query params**

- `drone_id` optional
- `limit` optional, default `20`, max `100`

**Response 200**

```json
{
  "items": [
    {
      "cmd_id": "6f2d6b95-b21a-4d2c-8c67-b9a1687bbcb1",
      "drone_id": "HW-001",
      "command": "ARM",
      "status": "ACKED",
      "attempt_count": 1,
      "created_at": "2026-03-01T12:00:00Z"
    }
  ]
}
```

### `GET /api/fleet/health`

**Purpose**

- provide aggregate fleet health summary for the fleet page

**Response 200**

```json
{
  "healthy": 0,
  "warning": 0,
  "critical": 0,
  "offline": 0,
  "details": []
}
```

---

## Socket.IO Event Contract

These are the canonical Socket.IO event names for v4. Do not rename them ad hoc in client or server code.

### `fleet_telemetry`

```json
{
  "drone_id": "HW-001",
  "position": { "lat": 28.6139, "lon": 77.2090, "alt_m": 12.0 },
  "battery_pct": 86,
  "armed": false,
  "mode": "GUIDED",
  "gps_sats": 8,
  "ekf_ok": true,
  "source": "HARDWARE",
  "health_score": 0.86,
  "health_status": "GREEN",
  "timestamp": 1772366400.0
}
```

### `command_status`

```json
{
  "cmd_id": "6f2d6b95-b21a-4d2c-8c67-b9a1687bbcb1",
  "drone_id": "HW-001",
  "command": "ARM",
  "status": "REQUESTED",
  "attempt_count": 0,
  "accepted": true,
  "rejection_reason": null,
  "latency_ms": null,
  "timeline_event": "COMMAND_REQUESTED",
  "timestamp": 1772366400.0
}
```

### `system_alert`

```json
{
  "alert_id": "4c9914aa-50b3-4c71-93ec-9f0f0a47b0d4",
  "severity": "CRITICAL",
  "code": "BATTERY_LOW",
  "drone_id": "HW-001",
  "message": "Battery below threshold",
  "details": {},
  "timestamp": 1772366400.0
}
```

### `mission_state`

```json
{
  "mission_id": "M-001",
  "mission_state": "PLANNING",
  "mission_type": "PATROL",
  "drone_count": 1,
  "timestamp": 1772366400.0
}
```

### `service_status`

```json
{
  "mqtt": true,
  "database": true,
  "inventory": true,
  "environment": "HARDWARE",
  "timestamp": 1772366400.0
}
```

### W10 binding rule

- `AppShell` subscribes to `service_status`
- dashboard binds `fleet_telemetry`, `command_status`, and `system_alert`
- mission pages bind `mission_state`

---

## v4 UI Store Contract

v4 reuses the current Zustand stores additively. W10 does not introduce a full new global store layer.

### Reuse as-is or additive extension

- `fleetStore`: remains the live drone cache; extend entries with `health_score`, `health_status`, `source`, and `environment`
- `commandStore`: remains the command cache; extend entries with `status`, `attempt_count`, `timeline_event`, and optional `timeline`
- `eventStore`: remains the human-readable event feed; populate from `system_alert` and user-facing system messages
- `selectionStore`: reused as-is for selected drone IDs
- `uiStore`: reused as-is for filters, confirm dialog, and bottom strip tab state
- `missionStore`: reused for single active mission planning only; do not add true multi-mission state in W10

### `AppShell` ownership

`AppShell` owns:

- socket connect / disconnect lifecycle
- route layout state
- future auth bootstrap

These concerns should not be duplicated into the existing stores during W10.

---

## Persistence Model

### Core tables

- `events`
- `commands`
- `missions`
- `mission_plans`
- `drone_metrics`
- `operators` (when auth enabled)
- `audit_log` (when auth enabled)

### Principles

- Append-only event logging
- Queryable command history
- Rebuildable state after restart
- Minimal schema first, extensible later

### Snapshotting

- Snapshots are useful for rebuild speed
- Add them after base event append/query is working
- Do not let snapshot complexity block initial persistence delivery

This keeps the first persistence slice practical.

### W10 `commands` table fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `cmd_id` | UUID | Yes | Primary key and public command identifier |
| `drone_id` | VARCHAR(64) | Yes | Target drone ID |
| `command` | VARCHAR(32) | Yes | Uppercase verb, e.g. `ARM` |
| `status` | VARCHAR(24) | Yes | `REQUESTED`, `RETRYING`, `ACKED`, `FAILED`, `REJECTED` |
| `params_json` | JSONB | No | Command parameters; default `{}` |
| `attempt_count` | INTEGER | Yes | Starts at `0`, increments per send attempt |
| `requested_by` | VARCHAR(64) | No | Placeholder identity until auth is enabled |
| `client_request_id` | VARCHAR(64) | No | Optional idempotency/correlation key |
| `preflight_snapshot_json` | JSONB | No | Captured preflight values at request time |
| `rejection_reason` | TEXT | No | Present when command is rejected |
| `requested_at` | TIMESTAMPTZ | Yes | Request creation time |
| `last_attempt_at` | TIMESTAMPTZ | No | Most recent publish attempt time |
| `completed_at` | TIMESTAMPTZ | No | Set on ACK/final failure/rejection |
| `created_at` | TIMESTAMPTZ | Yes | Row creation time |
| `updated_at` | TIMESTAMPTZ | Yes | Row update time |

### W10 `events` table fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `event_id` | UUID | Yes | Primary key |
| `event_type` | VARCHAR(48) | Yes | e.g. `COMMAND_REQUESTED`, `COMMAND_REJECTED` |
| `aggregate_type` | VARCHAR(32) | Yes | `COMMAND`, `DRONE`, `MISSION`, `SYSTEM` |
| `aggregate_id` | VARCHAR(64) | Yes | Public ID of the aggregate |
| `drone_id` | VARCHAR(64) | No | Present for drone-related events |
| `command_id` | UUID | No | Foreign key to `commands.cmd_id` when event belongs to a command |
| `mission_id` | VARCHAR(64) | No | Reserved for future mission events |
| `severity` | VARCHAR(16) | No | Optional for alerts: `INFO`, `WARNING`, `CRITICAL` |
| `payload_json` | JSONB | Yes | Event-specific structured payload |
| `requested_by` | VARCHAR(64) | No | Placeholder identity until auth is enabled |
| `created_at` | TIMESTAMPTZ | Yes | Event append time |

---

## Mission Model

### Immediate scope

- Single active mission execution
- Rich mission planning UI
- Stored mission plans and history

### Deferred functional scope

- True concurrent multi-mission execution
- Cross-mission scheduling
- Reservation and conflict resolution

### Why this matters

Multi-mission is not just a UI change. It requires:

- drone reservation logic
- conflict policy
- preemption rules
- rollback semantics

Until those are explicitly implemented, the UI may preview the concept but the backend should remain single-active-mission first.

---

## Auth and Authorization Strategy

### Correct framing

You are partly right: auth and authz can be introduced in a later hardening phase, but only if the system is shaped for it now.

### What can be deferred

- full login workflow
- password lifecycle
- role management UI
- token rotation and refresh

### What should not be deferred in design

- operator identity field in command/audit models
- request context hooks for future role checks
- endpoint boundaries that can accept auth middleware later
- audit-ready event structure

### Practical recommendation

Build the backend so auth slots in cleanly, but do not block functional delivery on full auth UX.

That is the right tradeoff for your stated priority.

---

## v3 Reuse Boundary

The v4 scaffold is side-by-side, but it does not start from zero. These reuse rules remove guesswork.

### Reuse in W10

- Reuse `poc/src/domain/telemetry.py` as the preferred telemetry value-object baseline
- Reuse `poc/src/ports/message_broker.py` as the broker interface baseline
- Reuse `poc/src/adapters/memory_broker.py` for tests and local command-path verification
- Reuse or wrap `poc/src/adapters/mqtt_broker.py` only behind the v4 messaging service boundary

### Do not reuse directly in W10

- Do not import Flask routes from `poc/mission_control_v3.py`
- Do not reuse v3 module-level state such as in-memory mission globals, command dictionaries, or event ring buffers
- Do not couple v4 APIs to the current v3 response shapes unless explicitly documented

### Deferred reuse

- Fault-injection models under `poc/src/domain/` are not required for the first v4 functional slice
- Integrate those later only if simulator or fault-testing scenarios need them

The rule is simple: reuse portable domain/value abstractions, do not reuse v3 runtime globals.

---

## Delivery Order

### Phase 1: v4 skeleton

1. Create `poc/v4_mission_control/`
2. Create `ui/src/v4/`
3. Add routed app shell

### Phase 2: safe command path

1. Centralized config
2. Preflight validation
3. Command retry and audit persistence
4. Fleet health view

### Phase 3: mission planning

1. Single mission planner
2. Save and load
3. Timeline and command detail UI

### Phase 4: hardening

1. Basic auth
2. Role checks
3. Operational docs
4. Scale and resilience improvements

This order matches your actual priority: functionality first, then hardening.

---

## Open Risks To Track

- Topic namespacing becomes expensive if introduced after many producers are built
- Event schema can bloat if commands and telemetry are not normalized early
- If auth is deferred too long, operators and audit fields can become awkward retrofits
- If the v4 app is not built side-by-side, v3 regressions will slow delivery

---

## Summary

The pragmatic v4 architecture is:

- side-by-side with v3
- FastAPI backend
- React routed UI
- Socket.IO for real-time
- PostgreSQL for persistence
- centralized safety config
- deployment-level environment separation
- single-mission functional delivery first
- auth-ready structure, full auth hardening later

---

## Source Links

- UI source of truth: `V4_INTERFACE_STORYBOARD.md`
- Current simulator stack: `ops/docker-compose.yml`
- Current hardware stack: `ops/docker-compose.hardware.yml`
- Current v3 backend: `poc/mission_control_v3.py`
