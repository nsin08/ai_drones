# Mission Control v4 — Design Document

**Version:** 1.0  
**Date:** 2026-03-02  
**Branch base:** `feature/04-mission-control-v4`  
**Author:** ai_drones team

---

## 1. System Overview

Mission Control v4 is a FastAPI-based backend that manages a drone fleet through a structured command-and-event pipeline. It replaces the Flask v3 prototype with:

- **Deterministic command safety** — every command passes through a preflight gate before acceptance
- **Event sourcing** — all state changes are recorded as immutable events; drone state can be reconstructed at any point
- **WebSocket real-time push** — operators receive live command status and health updates without polling
- **Multi-mission FSM** — up to N concurrent missions, each governed by a strict state machine
- **JWT authentication + RBAC** — ADMIN / PILOT / OBSERVER roles with per-drone assignment
- **Circuit breaker + MQTT reconnect** — graceful degradation when upstream services fail

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                React v4 UI (Vite + React 19)            │
│   Dashboard  Fleet  Commands  Missions  MissionBuilder  │
└────────────────────────┬───────────────┬────────────────┘
                    REST /api       WS /ws
                         │               │
┌────────────────────────▼───────────────▼────────────────┐
│              FastAPI Application  (poc/v4_mission_control)│
│                                                          │
│  api/routes.py  ←→  ServiceContainer (runtime.py)       │
│                          │                              │
│   ┌──────────────────────▼──────────────────────────┐   │
│   │           Service Layer                         │   │
│   │  PreflightService   CommandService              │   │
│   │  MissionService     HealthService               │   │
│   │  EventReplayService ServiceStatusService        │   │
│   └──────────┬──────────────────┬───────────────────┘   │
│              │                  │                        │
│   ┌──────────▼──────┐  ┌────────▼─────────┐             │
│   │   Repositories  │  │   WebSocketMgr   │             │
│   │  InMemory / SQL │  │  broadcast_sync  │             │
│   └──────────┬──────┘  └──────────────────┘             │
│              │                                           │
│   ┌──────────▼──────────────────────────────────────┐   │
│   │        PostgreSQL 16  (SQLAlchemy 2.0)          │   │
│   │  commands  events  missions  tasks              │   │
│   │  drones  drone_snapshots  operators             │   │
│   └─────────────────────────────────────────────────┘   │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │  Infrastructure                                  │  │
│   │  MqttReconnectClient  CircuitBreaker             │  │
│   └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │                             │
    MQTT broker                 Inventory service
    (mosquitto)                 (poc/inventory/)
```

---

## 3. State Machines

### 3.1 Command Status FSM

```
REQUESTED ──► RETRYING ──► ACKED
     │             │
     │             └──► TIMED_OUT
     │
     └──► FAILED   (via NACK)
```

**Transitions:**
| From | Event | To |
|------|-------|-----|
| REQUESTED | ACK received within timeout | ACKED |
| REQUESTED | timeout expires | RETRYING |
| RETRYING | ACK received | ACKED |
| RETRYING | max retries exhausted | TIMED_OUT |
| any active | NACK received | FAILED |

**Config:** `COMMAND_ACK_TIMEOUT_SEC=5`, `COMMAND_MAX_RETRIES=3`, `COMMAND_RETRY_BACKOFF_SEC=(1,2,4)`

---

### 3.2 Mission Status FSM

```
PLANNING ──► PLANNED ──► ACTIVE ──► COMPLETED
                              │
                              ▼
                            PAUSED ──► ACTIVE (resume)
                              │
                         any state ──► ABORTED
```

**Valid transitions:**
| From | Transition | To |
|------|-----------|-----|
| PLANNING | `plan` | PLANNED |
| PLANNED | `start` | ACTIVE |
| ACTIVE | `pause` | PAUSED |
| PAUSED | `resume` | ACTIVE |
| ACTIVE | `complete` | COMPLETED |
| PLANNING, PLANNED, ACTIVE, PAUSED | `abort` | ABORTED |

Invalid transitions raise `ValueError` and return HTTP 400.

---

### 3.3 Circuit Breaker FSM

```
CLOSED ──(3 failures)──► OPEN
  ▲                         │
  │              (reset_timeout=30s)
  │                         ▼
  └──(probe success)── HALF_OPEN
```

---

## 4. Event Sourcing

All state changes are recorded as immutable `Event` records in the `events` table.

### 4.1 Event Types

| Event | Trigger |
|-------|---------|
| `COMMAND_REQUESTED` | `CommandService.submit_command()` |
| `COMMAND_ACKED` | explicit ACK from drone |
| `COMMAND_RETRYING` | retry loop fires |
| `COMMAND_TIMED_OUT` | retries exhausted |
| `COMMAND_FAILED` | NACK received |
| `TELEMETRY_RECEIVED` | MQTT telemetry message |
| `MISSION_CREATED` | `MissionService.create_mission()` |
| `MISSION_PLANNED` | `MissionService.plan_mission()` |
| `MISSION_ACTIVE` | `MissionService.start_mission()` |
| `MISSION_PAUSED` | `MissionService.pause_mission()` |
| `MISSION_COMPLETED` | `MissionService.complete_mission()` |
| `MISSION_ABORTED` | `MissionService.abort_mission()` |

### 4.2 Snapshot Strategy

Every 100 events per `drone_id`, a `DroneSnapshot` is written with the full reconstructed state. State rebuild starts from the most recent snapshot, then replays only events after `snapshot.version_seq`.

---

## 5. API Contracts

### 5.1 Authentication

```
POST /api/auth/token
  Request:  { "username": str, "password": str }
  Response: { "access_token": str, "token_type": "bearer",
              "operator_id": str, "username": str, "role": str }

GET  /api/auth/me
  Header:   Authorization: Bearer <token>
  Response: { "operator_id", "username", "role", "allowed_drones": [...] }
```

### 5.2 Health

```
GET /api/health
  Response: { "status": "ok", "service": str, "environment": str,
              "timestamp": ISO8601, "mqtt_connected": bool|null,
              "inventory_available": bool|null }

GET /api/fleet/health
  Response: { "total": int, "healthy": int, "warning": int,
              "critical": int, "offline": int, "drones": [...] }

GET /api/drones/{id}/health
  Response: { "drone_id": str, "score": float, "label": GREEN|YELLOW|RED|OFFLINE,
              "battery_pct": int, "gps_sats": int, "ekf_ok": bool,
              "last_seen_sec": float }
```

### 5.3 Commands

```
POST /api/commands                           202 | 400
GET  /api/commands?drone_id=&limit=          200
GET  /api/commands/{cmd_id}                  200 | 404
POST /api/commands/{cmd_id}/ack              200 | 404
POST /api/commands/{cmd_id}/nack?reason=     200 | 404
```

### 5.4 Missions

```
POST /api/missions                           201
GET  /api/missions?status=                   200
GET  /api/missions/{id}                      200 | 404
POST /api/missions/{id}/plan                 200 | 400
POST /api/missions/{id}/start                200 | 400
POST /api/missions/{id}/pause                200 | 400
POST /api/missions/{id}/resume               200 | 400
POST /api/missions/{id}/complete             200 | 400
POST /api/missions/{id}/abort                200 | 400
```

### 5.5 WebSocket Events

Connect to `ws://host/ws`. Receive JSON messages:

```json
// command_status event
{ "event": "command_status", "cmd_id": "...", "drone_id": "SIM-001",
  "status": "ACKED", "attempt_count": 1 }

// drone_health event
{ "event": "drone_health", "drone_id": "SIM-001",
  "score": 0.82, "label": "GREEN", "battery_pct": 87, "gps_sats": 9 }

// service_status event
{ "event": "service_status", "mqtt": true, "inventory": false }
```

---

## 6. Database Schema

### Tables

| Table | Primary Key | Key Columns |
|-------|-------------|-------------|
| `commands` | `cmd_id` UUID | `drone_id`, `command`, `status`, `requested_by`, `created_at` |
| `events` | `event_id` UUID | `aggregate_id`, `event_type`, `payload_json`, `created_at` |
| `missions` | `mission_id` str | `type`, `status`, `config_json`, `created_by` |
| `tasks` | `task_id` str | `mission_id` FK, `drone_ids_json`, `type`, `state`, `waypoints_json`, `formation` |
| `drones` | `drone_id` str | `env`, `last_seen_at`, `last_telemetry_json`, `health_score`, `health_label` |
| `drone_snapshots` | `snapshot_id` int | `drone_id`, `version_seq`, `state_json` |
| `operators` | `operator_id` str | `username`, `role`, `hashed_password` |

### Migration

| Revision | Description |
|----------|-------------|
| `2c546c1e5c55` | Initial v4 schema — all 7 tables |

Run: `cd poc && alembic upgrade head`

---

## 7. Health Scoring Formula

```
health_score = min(battery_score, gps_score, ekf_score, signal_score)

battery_score  = battery_pct / 100.0
gps_score      = min(gps_sats / 8.0, 1.0)
ekf_score      = 1.0 if ekf_ok else 0.0
signal_score   = max(0.0, 1.0 - seconds_since_last_seen / STALE_TIMEOUT_SEC)

label:
  score ≥ 0.7              → GREEN
  0.3 ≤ score < 0.7        → YELLOW
  score < 0.3              → RED
  last_seen > stale_timeout → OFFLINE
```

---

## 8. Security Model

| Role | Permissions |
|------|------------|
| ADMIN | All endpoints |
| PILOT | Submit commands to assigned drones; read-only on others |
| OBSERVER | GET endpoints only; no command submission (HTTP 403) |

JWT tokens expire after `JWT_EXPIRE_MINUTES=60` (configurable).  
Set `AUTH_ENABLED=True` (env: `MC_V4_AUTH_ENABLED`) in production.

---

## 9. Infrastructure

### Circuit Breaker (Inventory)

Wraps HTTP calls to the inventory service. 3 consecutive failures → OPEN state; calls fail-fast with `CircuitOpenError`. After 30 s the breaker enters HALF_OPEN; one probe is allowed; success resets to CLOSED.

### MQTT Reconnect Backoff

`MqttReconnectClient` retries with cycling schedule `[1, 5, 30]` seconds using `itertools.cycle`. A daemon thread drives the reconnect loop; the main application remains responsive.

### Environment Separation

| Setting | Value | Effect |
|---------|-------|--------|
| `DRONE_ENV=SIM` | default | Blocks HW-* drone commands |
| `DRONE_ENV=HARDWARE` | production | Blocks SIM-* drone commands |
| `DRONE_ENV=ALL` | dev/test | No guard |

---

## 10. Configuration Reference

All settings use the `MC_V4_` env-var prefix. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `MC_V4_ENVIRONMENT` | `SIM` | SIM or HARDWARE |
| `MC_V4_DRONE_ENV` | `ALL` | Command routing guard |
| `MC_V4_USE_DATABASE` | `false` | Enable PostgreSQL repos |
| `MC_V4_DATABASE_URL` | `postgresql+psycopg2://...` | DB connection string |
| `MC_V4_AUTH_ENABLED` | `false` | Require JWT Bearer tokens |
| `MC_V4_JWT_SECRET_KEY` | `dev-secret-...` | **Change in production** |
| `MC_V4_COMMAND_MAX_RETRIES` | `3` | Command retry limit |
| `MC_V4_STALE_TIMEOUT_SEC` | `30` | Drone offline threshold |
