# Mission Control v3 → v4 Migration Guide

**Date:** 2026-03-02  
**Applies to:** teams running the Flask-based v3 backend (`poc/mission_control.py`) and transitioning to the FastAPI v4 backend (`poc/v4_mission_control/`)

---

## 1. Overview of Changes

| Area | v3 | v4 |
|------|----|----|
| Framework | Flask + Flask-SocketIO | FastAPI + Uvicorn |
| DB | None (in-memory dict) | PostgreSQL 16 via SQLAlchemy 2.0 |
| Auth | None | JWT Bearer + RBAC |
| Command safety | Basic check | Full preflight gate + retry FSM |
| Real-time | Socket.IO | Native WebSocket |
| Config | Hardcoded | Pydantic Settings (`MC_V4_*` env vars) |
| MQTT topic | `fleet/{drone_id}` | `fleet/{env}/{drone_id}` |

---

## 2. Environment Variable Changes

### v3 variables (no prefix, informal)
```
MQTT_BROKER=localhost
MQTT_PORT=1883
```

### v4 replacements (`MC_V4_` prefix)
```bash
MC_V4_MQTT_TOPIC_PREFIX=fleet/sim      # was: implied in code
MC_V4_USE_DATABASE=true                # false = in-memory (dev/test)
MC_V4_DATABASE_URL=postgresql+psycopg2://v4:v4@localhost:5432/missioncontrol
MC_V4_AUTH_ENABLED=true                # false = open (dev only)
MC_V4_JWT_SECRET_KEY=<strong-secret>
MC_V4_ENVIRONMENT=SIM                  # or HARDWARE
MC_V4_DRONE_ENV=SIM                    # command routing guard
```

---

## 3. API Endpoint Changes

### 3.1 Renamed / restructured

| v3 endpoint | v4 equivalent | Notes |
|-------------|---------------|-------|
| `GET /health` | `GET /api/health` | `/api` prefix added |
| `POST /command` | `POST /api/commands` | Renamed; body schema changed |
| `GET /commands` | `GET /api/commands` | Same; added `?drone_id=&limit=` |
| `GET /fleet` | `GET /api/fleet/health` | Returns health scores, not raw list |

### 3.2 New in v4 (no v3 equivalent)

```
POST /api/auth/token         ← login
GET  /api/auth/me            ← current operator
GET  /api/drones/{id}/health
GET  /api/drones/{id}/preflight
POST /api/missions           ← mission management family
GET  /api/missions
GET  /api/missions/{id}
POST /api/missions/{id}/plan|start|pause|resume|complete|abort
GET  /api/commands/{cmd_id}
POST /api/commands/{cmd_id}/ack|nack
GET  /ws                     ← WebSocket (was Socket.IO)
```

### 3.3 Removed in v4

```
/socket.io/*    (Socket.IO transport replaced by native WS)
```

---

## 4. Request / Response Schema Changes

### 4.1 Command request

**v3:**
```json
{ "drone_id": "SIM-001", "command": "ARM" }
```

**v4:**
```json
{
  "drone_id": "SIM-001",
  "command": "ARM",
  "params": {},          ← new optional field
  "requested_by": null   ← stamped from JWT if auth enabled
}
```

### 4.2 Command response

**v3:**
```json
{ "ok": true }
```

**v4 (accepted):**
```json
{
  "status": "REQUESTED",
  "cmd_id": "3f8a...",
  "drone_id": "SIM-001",
  "command": "ARM"
}
```

**v4 (rejected):**
```json
{
  "status": "REJECTED",
  "drone_id": "SIM-001",
  "command": "ARM",
  "rejection_reason": "battery below minimum threshold (5% < 10%)"
}
```

---

## 5. Real-Time Transport Migration

### v3: Socket.IO

```javascript
// v3 client
const socket = io('http://localhost:5000');
socket.on('command_update', (data) => { ... });
```

### v4: Native WebSocket

```javascript
// v4 client
const ws = new WebSocket('ws://localhost:5000/ws');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.event === 'command_status') { ... }
  if (msg.event === 'drone_health')   { ... }
  if (msg.event === 'service_status') { ... }
};
```

The React v4 shell (`ui/src/v4/socket.js`) already implements the v4 WebSocket pattern.

---

## 6. MQTT Topic Schema Changes

### v3
```
fleet/SIM-001/telemetry
fleet/SIM-001/command
```

### v4
```
fleet/sim/SIM-001/telemetry    ← env segment added
fleet/sim/SIM-001/command
fleet/sim/SIM-001/ack
```

**Action required:** Update `swarmsim/swarmsim.py` and any hardware drone firmwares to publish/subscribe to the new `fleet/{env}/{drone_id}/*` topics. Set `MC_V4_MQTT_TOPIC_PREFIX=fleet/sim` for SIM, `fleet/hardware` for HARDWARE.

---

## 7. Database Setup (new in v4)

v3 had no database. v4 requires PostgreSQL 16.

```bash
# Start the database container
cd ops
docker compose -f docker-compose.v4.yml up -d postgres

# Run migrations
cd poc
alembic upgrade head

# Seed test data (optional)
python -c "from poc.v4_mission_control.db.seed import seed_all; seed_all()"
```

To keep using in-memory repos during development:
```bash
MC_V4_USE_DATABASE=false  # default
```

---

## 8. Authentication Migration

v3 had no auth. v4 ships with auth **disabled by default** (`AUTH_ENABLED=false`).

### Enable auth in production
```bash
export MC_V4_AUTH_ENABLED=true
export MC_V4_JWT_SECRET_KEY=$(openssl rand -hex 32)
```

### Seeded dev credentials (in-memory operator store)

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin-secret` | ADMIN |
| `pilot1` | `pilot1-secret` | PILOT (SIM-001..SIM-010) |
| `pilot2` | `pilot2-secret` | PILOT (SIM-011..SIM-020) |
| `observer` | `observer-secret` | OBSERVER |

**Important:** The in-memory operator store is for development only. Production deployments must switch to a proper user store backed by the `operators` DB table.

---

## 9. Docker Compose Changes

**v3:** `ops/docker-compose.yml` (broker only)

**v4:** `ops/docker-compose.v4.yml` (broker + postgres + v4 app)

Extend your deployment:
```bash
docker compose -f ops/docker-compose.v4.yml up -d
```

Key service names:
| Service | Port | Description |
|---------|------|-------------|
| `mqtt` | 1883 | Mosquitto MQTT broker |
| `postgres` | 5432 | PostgreSQL 16 |
| `mission-control-v4` | 5000 | FastAPI v4 backend |

---

## 10. Backward Compatibility Layer

v3 endpoints (`/health`, `/command`, `/commands`, `/fleet`) are **not proxied** by v4. If you have existing tooling that hits v3 URLs, you have two options:

1. **Run both side by side** — v3 on port 5000, v4 on port 5001 during transition
2. **URL rewrite in nginx** — proxy `/health` → `/api/health`, `/command` → `/api/commands`, etc.

Example nginx rewrite:
```nginx
location = /health   { proxy_pass http://v4:5001/api/health; }
location = /commands { proxy_pass http://v4:5001/api/commands; }
location /socket.io  { proxy_pass http://v3:5000; }  # v3 socket.io still used
```

---

## 11. Python Client SDK Changes

If you have scripts calling the v3 Python API directly:

```python
# v3 pattern
import requests
resp = requests.post("http://localhost:5000/command",
                     json={"drone_id": "SIM-001", "command": "ARM"})

# v4 pattern (with auth)
import requests

# 1. Get token
login = requests.post("http://localhost:5000/api/auth/token",
                      json={"username": "pilot1", "password": "pilot1-secret"})
token = login.json()["access_token"]

# 2. Submit command
resp = requests.post("http://localhost:5000/api/commands",
                     json={"drone_id": "SIM-001", "command": "ARM"},
                     headers={"Authorization": f"Bearer {token}"})
# 202 = accepted, 400 = rejected by preflight
```
