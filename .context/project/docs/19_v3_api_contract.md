# V3 API Contract (REST + Socket.IO)

**Last Updated:** February 7, 2026  
**Scope:** Canonical API contract for the V3 Mission Control SPA. This document is a single source of truth for request/response schemas, errors, and realtime events.

---

## 1) Conventions

**Base URL:** `http://localhost:5000`  
**Content-Type:** `application/json`  
**Time:** Unix epoch seconds (`timestamp` as float)  
**IDs:** `drone_id` are stable strings (e.g., `D001`, `ops-drone-1`)  

**ID namespaces (to prevent collisions)**
- SwarmSim drones: `SIM-###` (e.g., `SIM-001`)
- SITL drones: `SITL-###` or `ops-drone-#` (existing)
- Hardware drones: `HW-###` (or real serial-based IDs)

**Staleness policy**
- A drone is considered **stale** if `now - last_seen > STALE_SEC` (default 30s).
- Stale drones remain in inventory with `stale=true` until removed by operator or TTL (optional).

**Error envelope (all non-2xx)**
```json
{
  "error": "string",
  "code": "STRING_CODE",
  "detail": "optional string"
}
```

**Pagination (optional for roster)**
- Query: `?page=1&page_size=50`
- Response: `page`, `page_size`, `total`

---

## 2) REST Endpoints

### GET `/api/inventory`

**Query (optional)**
- `page` (int)
- `page_size` (int, default 50, max 200)
- `status` (ACTIVE|DISABLED|UNKNOWN)
- `role` (LEADER|POINT_MAN|WINGMAN|SCOUT|RELAY|GUARD|CARGO)
- `source` (SITL|SWARMSIM|EDGE_AGENT|UNKNOWN)

**Response 200**
```json
{
  "items": [
    {
      "drone_id": "D001",
      "status": "ACTIVE",
      "battery_pct": 87.2,
      "position": {"lat": 28.6139, "lon": 77.2090, "alt_m": 50.0},
      "mode": "AUTO",
      "armed": true,
      "current_role": "LEADER",
      "last_seen": 1700000000.0,
      "stale": false,
      "source": "SITL"
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 14
}
```

**Errors**
- 503 `INVENTORY_UNAVAILABLE`

---

### GET `/api/inventory/{drone_id}`

**Response 200**
```json
{
  "drone_id": "D001",
  "status": "ACTIVE",
  "battery_pct": 87.2,
  "position": {"lat": 28.6139, "lon": 77.2090, "alt_m": 50.0},
  "mode": "AUTO",
  "armed": true,
  "current_role": "LEADER",
  "last_seen": 1700000000.0,
  "stale": false,
  "source": "SITL"
}
```

**Errors**
- 404 `DRONE_NOT_FOUND`
- 503 `INVENTORY_UNAVAILABLE`

---

### GET `/api/missions`

**Response 200**
```json
{
  "available_missions": ["PATROL","ESCORT","PERIMETER"],
  "current_mission": "PATROL",
  "mission_state": "IDLE|PLANNING|PLANNED|ACTIVE|PAUSED|ABORTED|COMPLETED",
  "mission_config": {
    "PATROL": {"drone_count": 5, "team_type": "PATROL"}
  }
}
```

---

### POST `/api/mission/assign`

Assign selected drones + roles to a mission (no planning).

**Request**
```json
{
  "mission_type": "PATROL",
  "drone_ids": ["D001","D002"],
  "role_map": {"D001":"LEADER","D002":"WINGMAN"}
}
```

**Response 200**
```json
{
  "status": "success",
  "mission_type": "PATROL",
  "assigned": 2
}
```

**Errors**
- 400 `INVALID_MISSION`
- 400 `DRONE_IDS_REQUIRED`

---

### POST `/api/mission/plan`

Validate and preview mission plan before start.

**Request**
```json
{
  "mission_type": "PATROL",
  "group_id": "G01",
  "drone_ids": ["D001","D002"],
  "plan": { "type": "PATROL", "waypoints": [{"lat":12.34,"lon":56.78,"alt_m":50.0}] }
}
```

**Response 200**
```json
{
  "ok": true,
  "mission_id": "M001",
  "plan_preview": {
    "D001": {"waypoints": [{"lat":12.34,"lon":56.78,"alt_m":50.0}]},
    "D002": {"waypoints": [{"lat":12.3405,"lon":56.7805,"alt_m":50.0}]}
  },
  "warnings": []
}
```

**Errors**
- 400 `INVALID_PLAN`

---

### POST `/api/mission/start`

Start a planned mission (publishes per-drone `UPLOAD_MISSION` + commands).

**Request**
```json
{
  "mission_id": "M001",
  "mission_type": "PATROL",
  "drone_ids": ["D001","D002"]
}
```

**Response 200**
```json
{
  "ok": true,
  "mission_id": "M001",
  "started": 2,
  "failed": 0,
  "errors": [],
  "mission_state": "ACTIVE"
}
```

**Errors**
- 400 `INVALID_MISSION`
- 409 `MISSION_ALREADY_ACTIVE`

**Mission start flow (UPLOAD_MISSION semantics)**
1. Backend validates mission + drones.
2. Backend publishes MQTT commands internally:
   - `fleet/{drone_id}/command` with `command=UPLOAD_MISSION`
   - One command per drone with unique `cmd_id`
3. Backend waits up to `START_ACK_TIMEOUT_SEC` (default 5s) for ACKs.
4. Response includes `started`, `failed`, and `errors` entries.

**Note:** `UPLOAD_MISSION` is **not** a REST endpoint. It is an internal MQTT command used by mission/start.

---

### POST `/api/mission/reassign_leader`

Reassign LEADER after a formation break.

**Request**
```json
{
  "mission_id": "M001",
  "new_leader_id": "D002"
}
```

**Response 200**
```json
{
  "ok": true,
  "mission_id": "M001",
  "new_leader_id": "D002",
  "mission_state": "ACTIVE"
}
```

**Errors**
- 400 `INVALID_LEADER`
- 409 `MISSION_NOT_ACTIVE`

---

### POST `/api/command/{hold|return|disable|enable|arm|disarm|set_role}`

**Request**
```json
{"drone_id":"D001", "role":"LEADER"}
```

**Response 200**
```json
{"cmd_id":"uuid","status":"requested","message":"..."}
```

**Errors**
- 400 `DRONE_ID_REQUIRED`
- 400 `ROLE_REQUIRED` (set_role)

---

### POST `/api/command/bulk/{hold|return|disable|enable|arm|disarm|set_role}`

Bulk swarm command (single confirm from UI).

**Request**
```json
{
  "drone_ids": ["D001","D002","D003"],
  "cmd_group_id": "uuid (optional)",
  "role": "LEADER (for set_role only)"
}
```

**Response 200**
```json
{
  "cmd_group_id": "uuid",
  "requested": 3,
  "failed": 0,
  "errors": []
}
```

**Errors**
- 400 `DRONE_IDS_REQUIRED`
- 400 `ROLE_REQUIRED` (set_role)

---

### GET `/api/state/snapshot`

Snapshot endpoint used on Socket.IO reconnect to recover state.

**Response 200**
```json
{
  "mission_state": "ACTIVE",
  "current_mission": "PATROL",
  "drones": [
    {"drone_id":"D001","status":"ACTIVE","last_seen":1700000000.0}
  ],
  "commands": [
    {"cmd_id":"uuid","result":"SUCCESS","timestamp":1700000001.2}
  ]
}
```

---

## 3) Socket.IO Event Catalog

**telemetry_update**
```json
{
  "drone_id": "D001",
  "timestamp": 1700000000.0,
  "latitude": 28.6139,
  "longitude": 77.2090,
  "altitude_m": 50.0,
  "battery_pct": 87.2,
  "status": "ACTIVE",
  "mode": "AUTO",
  "armed": true,
  "mission_role": "LEADER",
  "velocity_mps": 12.3,
  "gps_fix": 3,
  "satellites_visible": 12
}
```

**command_ack**
```json
{
  "cmd_id": "uuid",
  "cmd_group_id": "uuid (optional)",
  "drone_id": "D001",
  "command": "HOLD",
  "result": "SUCCESS|FAILED|TIMEOUT",
  "late": false,
  "timestamp": 1700000001.2,
  "detail": "optional string"
}
```

**mission_changed**
```json
{
  "mission_type": "PATROL",
  "mission_state": "ACTIVE|PAUSED|COMPLETED|ABORTED",
  "drone_count": 5,
  "team_type": "PATROL",
  "timestamp": "2026-02-07T12:00:00Z"
}
```

**leader_election**
```json
{
  "leader_id": "D001",
  "reason": "leader_down",
  "timestamp": "2026-02-07T12:05:00Z"
}
```

---

## 4) Reconnection Strategy (Client)

On Socket.IO reconnect:
1. Re-fetch `/api/inventory`
2. Re-fetch `/api/missions`
3. Fetch `/api/state/snapshot` to reconcile commands and mission state
4. Clear transient UI state (pending commands older than timeout)
