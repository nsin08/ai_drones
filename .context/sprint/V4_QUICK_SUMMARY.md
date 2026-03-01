# Mission Control v4 — Quick Summary

**GitHub Issue:** #4 (Epic)  
**Planned Duration:** 9 weeks  
**Target Release:** Production-ready with hardware safety + persistence  

---

## Top 10 Drawbacks in v3 (Real Problems)

| # | Problem | Impact | v4 Fix |
|---|---------|--------|--------|
| 1️⃣ | **No hardware safety checks** | ARM executed w/o prearm validation; dangerous | Preflight checks before every command |
| 2️⃣ | **Commands timeout & vanish** | Lost commands, no history, no retries | Persistent DB log + 3x retry logic |
| 3️⃣ | **Single mission only** | Can't run PATROL + ESCORT concurrently | Multi-mission with task decomposition |
| 4️⃣ | **Map is monitor-only** | Operators can't build missions in UI | Drag-to-waypoint + geofence editor |
| 5️⃣ | **In-memory state** | Restart = lose all history | Event sourcing + PostgreSQL |
| 6️⃣ | **Stale drone detection sucks** | Battery=2% still shows ACTIVE | Health scoring (battery, GPS, EKF, signal) |
| 7️⃣ | **No real command feedback** | User doesn't know if drone obeyed | Telemetry-driven state + command timeline |
| 8️⃣ | **No multi-user support** | Anyone can command; no audit | JWT auth + role-based ACL (PILOT/OBSERVER/ADMIN) |
| 9️⃣ | **No graceful degradation** | Inventory timeout = UI hangs | Circuit breaker + fallback to cached data |
| 🔟 | **SIM/PROD mixed** | Easy to accidentally command real drone | Topic routing: `fleet/{env}/{drone_id}` |

---

## v4 Architecture at a Glance

```
┌─────────────────────────────────────────────────┐
│            React UI (Interactive)               │
│   Mission builder + mission timeline + alerts   │
└──────────────────┬──────────────────────────────┘
                   │ WebSocket + JWT
┌──────────────────────────────────────────────────┐
│  FastAPI Backend + Async Command Pipeline        │
├──────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────┐    │
│  │ Command Router                          │    │
│  │ ├─ Preflight check (battery, GPS, etc) │    │
│  │ ├─ ACL check (role-based)               │    │
│  │ ├─ Retry (up to 3×)                    │    │
│  │ └─ Emit event → database                │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │ Multi-Mission State Machine              │    │
│  │ ├─ Mission { tasks: [...] }              │    │
│  │ ├─ Task FSM: PLANNED→ACTIVE→COMPLETED   │    │
│  │ └─ Per-drone role assignment            │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │ Event Sourcing + Health Scoring         │    │
│  │ ├─ Telemetry → health metric calc       │    │
│  │ ├─ Alert thresholds (RED/YELLOW/GREEN) │    │
│  │ └─ Event stream → database              │    │
│  └─────────────────────────────────────────┘    │
└────────┬────────────────────────────────┬───────┘
         │ MQTT                           │ SQL
    ┌────────────┐              ┌─────────────────┐
    │  Mosquitto │              │  PostgreSQL     │
    │  Broker    │              │  - Commands     │
    └────────────┘              │  - Events       │
                                │  - Missions     │
                                │  - Audit trail  │
                                └─────────────────┘
```

---

## Key Innovations

### 1. **Preflight-Aware Commands**
```python
# Before v3: send("arm", drone_id) → hope it works
# v4:
preflight = drone.health_check()
if preflight.battery_pct < 10:
    reject("battery too low")
elif preflight.ekf_ok is False:
    reject("EKF unhealthy")
else:
    cmd = send("arm", drone_id)
    retry_if_timeout(cmd, max_attempts=3)
```

### 2. **Persistent Command Audit**
```python
# v3: commands = {} dictionary (ephemeral)
# v4: 
Event.create(type="COMMAND_REQUESTED", drone_id="HW-001", command="arm")
Event.create(type="COMMAND_ACKED", drone_id="HW-001", result="SUCCESS")
# Query: /api/commands?drone_id=HW-001&limit=50 → full history
```

### 3. **Multi-Mission with Task Decomposition**
```python
mission = {
    "id": "M-001",
    "tasks": [
        {"task_id": "T-A", "drones": ["HW-001"], "type": "PATROL", ...},
        {"task_id": "T-B", "drones": ["HW-002"], "type": "ESCORT", ...},
    ]
}
# Each task has independent state machine
# Drone HW-001 tracks only task T-A; doesn't interfere with T-B
```

### 4. **Health Score + Alerts**
```python
health_score = min(
    battery_score,   # 100% = 1.0, 10% = 0.0
    gps_score,       # 4+ sats = 1.0, 0 sats = 0.0
    ekf_score,       # EKF OK = 1.0, unhealthy = 0.0
    signal_score     # last_seen < 5s = 1.0, > 30s = 0.0
)
# CRITICAL if score < 0.3 → (alarm + notification)
# YELLOW if 0.3 ≤ score < 0.7
# GREEN if score ≥ 0.7
```

### 5. **Role-Based Access**
```python
@app.post("/api/command/arm")
def arm_drone(token: str, drone_id: str):
    operator = jwt.decode(token)  # {id, role, ...}
    
    if operator.role == "OBSERVER":
        return {"error": "read-only; cannot issue commands"}, 403
    elif operator.role == "PILOT":
        if drone_id not in operator.allowed_drones:
            return {"error": "not assigned to this drone"}, 403
    
    # proceed to command validation...
```

---

## Sprint Structure (9 Weeks)

### W1-W2: Foundation
- S4-001: Database + SQLAlchemy + migrations
- S4-002: Event sourcing backend
- S4-003: Command validator + retry

### W3-W4: Mission Model
- S4-004: Multi-mission state machine
- S4-005: Drone health scoring

### W5-W6: UI + Auth
- S4-006: Interactive mission builder
- S4-007: Command feedback UX
- S4-008: JWT auth + audit trail

### W7-W8: Reliability
- S4-009: Circuit breaker + graceful degradation
- S4-010: Environment separation (SIM vs PROD)
- S4-011: Load testing + chaos engineering

### W9: Documentation
- S4-012: Architecture docs + operator runbook

---

## Tech Stack (Recommended)

| Layer | v3 | v4 |
|-------|----|----|
| **Backend API** | Flask | **FastAPI** (async, OpenAPI) |
| **Real-time** | SocketIO (ephemeral) | **WebSocket + Redis Pub/Sub** (scaled) |
| **Database** | In-memory dict | **PostgreSQL + SQLAlchemy ORM** |
| **Auth** | None | **PyJWT + python-jose** |
| **Event Log** | Ring buffer (200 max) | **PostgreSQL event_log table** |
| **Load Testing** | Manual | **Locust** (replay drone behaviors) |

---

## Success Metrics

```
✅ Hardware Safety: 100% command path has preflight check
✅ Persistence: 0 lost commands; 100% query-able history  
✅ Multi-Mission: 5 concurrent drones, diff roles, no cross-talk
✅ UI Health: <100ms update latency (p99) at 50 drones
✅ Reliability: graceful degrades if MQTT/DB unavailable
✅ Auth: audit trail shows operator_id for every command
✅ Test/Prod: one toggle switch → isolated environments
```

---

## Getting Started

1. Review [MISSION_CONTROL_V4_PLAN.md](./MISSION_CONTROL_V4_PLAN.md) for detailed spec
2. Create GitHub Project board linked to Issue #4
3. Start with S4-001 (Database setup)
4. Parallel: Create PR for `/poc/mission_control_v4.py` skeleton (FastAPI + SQLAlchemy models)
5. Pair-program first 2 tasks to establish coding patterns

---

## Questions?

- Why PostgreSQL vs SQLite? → PostgreSQL scales to 100+ drones; supports JSONB fields for flexibility
- Why FastAPI vs Flask? → Async/await native, built-in OpenAPI docs, better backpressure handling
- Keep v3 running? → Yes, parallel deploy; gradual migration of endpoints
- How to test hardware commands safely? → DroneSession mocks in pytest; CI in docker-compose.hardware.yml

