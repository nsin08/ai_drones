# Mission Control v4

FastAPI-based fleet management backend for ArduPilot drone fleets.

## Quick Start

### 1. Start Infrastructure

```bash
cd ops
docker compose -f docker-compose.v4.yml up -d
```

Services started:
| Service | Port | Description |
|---------|------|-------------|
| MQTT broker | 1883 | Mosquitto |
| PostgreSQL | 5432 | v4 database |
| Mission Control v4 | 5000 | FastAPI backend |

### 2. Run DB Migrations

```bash
cd poc
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
alembic upgrade head
```

### 3. Start the Backend (dev mode)

```bash
cd poc
uvicorn v4_mission_control.app:create_app --factory --reload --port 5000
```

### 4. Start the Fleet Simulator

```bash
cd sim
python fleet_simulator.py --broker localhost --drones 12
```

### 5. Open the UI

```bash
cd ui
npm install
npm run dev
# → http://localhost:5173
```

---

## Running Tests

```bash
cd poc
pytest                              # all 310+ tests
pytest tests/unit/                  # unit tests only
pytest tests/integration/           # integration + chaos + regression
pytest tests/integration/test_regression.py  # API regression smoke tests
```

---

## Load Testing

Requires the backend to be running at `localhost:5000`.

```bash
pip install locust

# Headless run — 50 users, 5/s spawn rate, 60s duration
locust -f tests/load/locustfile.py \
       --host=http://localhost:5000 \
       --users 50 --spawn-rate 5 \
       --run-time 60s --headless

# Web UI (opens browser dashboard at http://localhost:8089)
locust -f tests/load/locustfile.py --host=http://localhost:5000
```

**DoD targets:**
- 50 concurrent users  
- 100+ events/sec sustained  
- p99 response latency < 100 ms  
- 0% failure rate on green-path endpoints

---

## Configuration

All settings use the `MC_V4_` environment variable prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `MC_V4_USE_DATABASE` | `false` | `true` = PostgreSQL; `false` = in-memory (tests) |
| `MC_V4_DATABASE_URL` | `postgresql+psycopg2://v4:v4@localhost:5432/missioncontrol` | DB connection |
| `MC_V4_ENVIRONMENT` | `SIM` | `SIM` or `HARDWARE` |
| `MC_V4_DRONE_ENV` | `ALL` | Command routing guard: `SIM` / `HARDWARE` / `ALL` |
| `MC_V4_AUTH_ENABLED` | `false` | `true` = require JWT Bearer tokens |
| `MC_V4_JWT_SECRET_KEY` | `dev-secret-...` | **Change in production** |
| `MC_V4_COMMAND_MAX_RETRIES` | `3` | Command retry limit |
| `MC_V4_STALE_TIMEOUT_SEC` | `30` | Seconds before a drone is considered OFFLINE |

---

## API reference (summary)

```
# Auth
POST /api/auth/token              Login → JWT
GET  /api/auth/me                 Current operator info

# Health
GET  /api/health                  Service liveness + MQTT/inventory status
GET  /api/fleet/health            Fleet-wide health summary
GET  /api/drones/{id}/health      Per-drone health score + label
GET  /api/drones/{id}/preflight   Preflight check result

# Commands
POST /api/commands                Submit command (preflight-gated)
GET  /api/commands                Command history
GET  /api/commands/{id}           Single command
POST /api/commands/{id}/ack       ACK a command
POST /api/commands/{id}/nack      NACK (force FAILED)

# Missions
POST /api/missions                Create mission
GET  /api/missions                List missions
GET  /api/missions/{id}           Mission detail
POST /api/missions/{id}/plan      PLANNING → PLANNED
POST /api/missions/{id}/start     PLANNED → ACTIVE
POST /api/missions/{id}/pause     ACTIVE → PAUSED
POST /api/missions/{id}/resume    PAUSED → ACTIVE
POST /api/missions/{id}/complete  ACTIVE → COMPLETED
POST /api/missions/{id}/abort     Any → ABORTED

# WebSocket
GET  /ws                          Real-time event stream
```

WebSocket events: `command_status`, `drone_health`, `service_status`

---

## Default dev credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | ADMIN |
| `pilot1` | `pilot123` | PILOT (SIM-001–SIM-006) |
| `pilot2` | `pilot123` | PILOT (SIM-007–SIM-012) |
| `observer` | `observe123` | OBSERVER |

---

## Project Layout

```
poc/v4_mission_control/
├── api/           REST routes + WS endpoint
├── auth/          JWT, RBAC, operator store
├── db/            Session factory, Alembic migrations, seed
├── events/        Event type constants
├── infra/         CircuitBreaker, MqttReconnectClient
├── models/        SQLAlchemy ORM models
├── repos/         In-memory + SQL repositories
├── schemas/       Pydantic request/response models
├── services/      Business logic (commands, missions, health, ...)
├── ws/            WebSocketManager
├── app.py         FastAPI app factory
└── config.py      Pydantic settings

poc/tests/
├── unit/          Fast in-memory unit tests (267 tests)
├── integration/   Chaos, regression, concurrent mission tests (45 tests)
└── load/          Locust load test scenarios
```

---

## Documentation

| Document | Location |
|----------|----------|
| Architecture & API contracts | [V4_DESIGN_DOC.md](../../.context/project/V4_DESIGN_DOC.md) |
| v3 → v4 migration guide | [V4_MIGRATION_GUIDE.md](../../.context/project/V4_MIGRATION_GUIDE.md) |
| Operator runbook | [V4_OPERATOR_RUNBOOK.md](../../.context/project/V4_OPERATOR_RUNBOOK.md) |
| Sprint plan | [V4_GAP_SPRINT_PLAN.md](../../.context/sprint/V4_GAP_SPRINT_PLAN.md) |
