# Mission Control v4 — Operator Runbook

**Version:** 1.0  
**Date:** 2026-03-02  
**Applies to:** `poc/v4_mission_control/` — FastAPI v4 backend  
**Audience:** Field operators and on-call engineers

---

## Quick Reference (Emergency)

| Symptom | First action | Section |
|---------|-------------|---------|
| ARM rejected — battery low | Check battery level on drone; charge to ≥ 10% | §2.1 |
| ARM rejected — calibration required | Run compass + IMU calibration via Mission Planner | §2.2 |
| ARM rejected — GPS insufficient | Wait for ≥ 4 satellites or move to open sky | §2.3 |
| Drone health shows RED | Inspect battery, GPS, EKF status | §3 |
| Drone shows OFFLINE | Check MQTT connectivity; restart `fleet_simulator.py` | §4.1 |
| Command stuck in RETRYING | Check drone ACK pipeline; or NACK manually | §5.1 |
| MQTT broker down | Restart mosquitto container | §6.1 |
| Mission won't start | Verify mission is in PLANNED state | §7.1 |
| Auth 401 — invalid token | Re-login via `POST /api/auth/token` | §8.1 |
| Auth 403 — permission denied | Verify operator role and drone assignment | §8.2 |

---

## 1. System Start-Up

### 1.1 Start all services

```bash
cd ops
docker compose -f docker-compose.v4.yml up -d
```

Services:
- **mqtt** → `localhost:1883` (Mosquitto MQTT broker)
- **postgres** → `localhost:5432` (PostgreSQL 16)
- **mission-control-v4** → `localhost:5000` (FastAPI backend)

### 1.2 Run DB migrations (first deployment only)

```bash
cd poc
. .venv/bin/activate   # or .venv\Scripts\activate on Windows
alembic upgrade head
```

### 1.3 Verify the backend is healthy

```bash
curl http://localhost:5000/api/health
# Expected:
# { "status": "ok", "environment": "SIM", "mqtt_connected": true, ... }
```

### 1.4 Start the fleet simulator

```bash
cd sim
python fleet_simulator.py --broker localhost --drones 12
```

---

## 2. Preflight Failures (ARM Rejection)

### 2.1 Battery below minimum (`battery_pct < 10%`)

**Symptom:**
```json
{ "status": "REJECTED", "rejection_reason": "battery below minimum threshold (5% < 10%)" }
```

**Resolution:**
1. Physically charge the drone battery to ≥ 15% before arming
2. If battery reading looks wrong, re-connect telemetry and wait 30 s for fresh data
3. For SIM drones: update the battery percentage in the simulator config

**Threshold:** `MC_V4_BATTERY_ARM_MIN_PCT` (default: 10)

---

### 2.2 Calibration required

**Symptom:**
```json
{ "rejection_reason": "calibration required" }
```

**Resolution:**
1. Open Mission Planner → Mandatory Hardware → Compass Calibration
2. Run Accelerometer Calibration
3. Reboot the drone flight controller
4. Wait for the telemetry to report `calibration_ok: true`

---

### 2.3 Insufficient GPS (`gps_sats < 4`)

**Symptom:**
```json
{ "rejection_reason": "insufficient GPS satellites (2 < 4)" }
```

**Resolution:**
1. Move the drone to an open outdoor area with clear sky view
2. Wait 60–120 s for GPS lock (typically 6–10 satellites)
3. Indoor operations require GPS-denied mode (set DRONE_GPS_BYPASS in config)

**Threshold:** `MC_V4_GPS_ARM_MIN_SATS` (default: 4)

---

### 2.4 EKF unhealthy

**Symptom:**
```json
{ "rejection_reason": "EKF health check failed" }
```

**Resolution:**
1. Place drone on a flat, stable surface
2. Reboot the flight controller
3. Ensure the IMU is not exposed to vibration or magnetic interference
4. Check for nearby motors or power cables that could cause interference
5. If EKF error persists after reboot, run full IMU calibration in Mission Planner

---

## 3. Drone Health Alerts

### Health score formula reference

```
score = min(battery/100, min(gps_sats/8, 1), ekf_ok ? 1.0 : 0.0,
            max(0, 1 - seconds_since_last_seen/30))

GREEN   score ≥ 0.7   normal operation
YELLOW  0.3 ≤ score < 0.7   watch carefully
RED     score < 0.3   do not arm; ground the drone
OFFLINE last_seen > 30s   telemetry link lost
```

### 3.1 Escalation thresholds

| Label | Action |
|-------|--------|
| GREEN | Normal operations |
| YELLOW | Monitor; plan to land if score drops |
| RED | Abort active mission immediately; do not arm |
| OFFLINE | Investigate telemetry link before any action |

```bash
# Check fleet-wide health
curl http://localhost:5000/api/fleet/health

# Check one drone
curl http://localhost:5000/api/drones/SIM-001/health
```

---

## 4. Telemetry / Connectivity Issues

### 4.1 Drone shows OFFLINE

**Definition:** No telemetry received in the last 30 s (`MC_V4_STALE_TIMEOUT_SEC`).

**Checklist:**
1. Confirm MQTT broker is running: `docker ps | grep mqtt`
2. Confirm the drone is publishing on `fleet/sim/{drone_id}/telemetry` (SIM) or `fleet/hardware/{drone_id}/telemetry` (HW)
3. Check for network partition between drone and broker
4. For SIM: confirm `fleet_simulator.py` is running with the correct `--broker` address
5. If broker was restarted, wait up to 30 s for the reconnect backoff loop to fire

---

### 4.2 MQTT service_status badge shows OFFLINE

**Symptom:** UI header shows red "MQTT: OFFLINE" badge.

**Backend circuit:**
1. `MqttReconnectClient` fires `on_disconnect` callback
2. `ServiceStatusService.report_mqtt_disconnected()` sets state to False
3. WebSocket `service_status` event broadcasts `{ "mqtt": false }` to all clients

**Resolution:**
1. Check broker: `docker logs ops-mqtt-1`
2. Restart if needed: `docker compose -f ops/docker-compose.v4.yml restart mqtt`
3. The client's reconnect loop will automatically retry every 1 → 5 → 30 s (cycling)
4. Once reconnected, the badge turns green automatically (no page refresh needed)

---

## 5. Command Pipeline Issues

### 5.1 Command stuck in RETRYING

**Symptom:** Command status is `RETRYING` and does not advance.

**Cause:** The drone is not acknowledging commands (link issue or drone firmware problem).

**Resolution options:**

**Option A — Wait for auto-timeout:**
The retry loop fires at backoff `(1, 2, 4)` s. After 3 attempts without ACK the command transitions to `TIMED_OUT` automatically.

**Option B — Force NACK immediately:**
```bash
# Find the cmd_id from history
curl http://localhost:5000/api/commands?drone_id=SIM-001

# Force fail it
curl -X POST "http://localhost:5000/api/commands/{CMD_ID}/nack?reason=operator+override"
```

---

### 5.2 Command rejected — wrong environment

**Symptom:**
```json
{ "rejection_reason": "SIM drone SIM-001 not allowed in HARDWARE environment" }
```

**Resolution:** This is a safety guard. Either:
- Switch `MC_V4_DRONE_ENV` to `ALL` for mixed environments
- Use only HARDWARE drone IDs (prefix `HW-`) when `DRONE_ENV=HARDWARE`

---

## 6. Infrastructure Failures

### 6.1 MQTT broker down

```bash
# Check
docker ps -a | grep mqtt

# Restart
docker compose -f ops/docker-compose.v4.yml restart mqtt

# Verify
mosquitto_pub -h localhost -t test -m hello
```

Expected recovery: The backend reconnects within 1–30 s via the backoff loop.

---

### 6.2 PostgreSQL unavailable

```bash
# Check
docker ps -a | grep postgres

# Restart
docker compose -f ops/docker-compose.v4.yml restart postgres

# Verify
psql postgresql://v4:v4@localhost:5432/missioncontrol -c "SELECT 1"
```

**During DB downtime:** If `USE_DATABASE=false`, the in-memory repos continue serving; no data loss for that session. If `USE_DATABASE=true`, API calls that require the DB will return 500. Read-only cached state is served from memory.

---

### 6.3 Backend returns 500

1. Check logs: `docker logs ops-mission-control-v4-1`
2. Look for `CRITICAL` or `ERROR` level messages
3. Common causes:
   - DB migration not run (`alembic upgrade head`)
   - Missing `MC_V4_JWT_SECRET_KEY` when `AUTH_ENABLED=true`
   - Port conflict on 5000

---

## 7. Mission Management

### 7.1 Connection: new PATROL mission (normal flow)

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"pilot1","password":"pilot1-secret"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Create mission
MISSION=$(curl -s -X POST http://localhost:5000/api/missions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type":"PATROL","tasks":[{"type":"WAYPOINT_NAV",
       "waypoints":[{"lat":28.61,"lng":77.2,"alt_m":30}],"formation":"V"}]}')
MID=$(echo $MISSION | python3 -c "import sys,json; print(json.load(sys.stdin)['mission_id'])")

# 3. Plan → Start
curl -X POST http://localhost:5000/api/missions/$MID/plan   -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:5000/api/missions/$MID/start  -H "Authorization: Bearer $TOKEN"

# 4. Check status
curl http://localhost:5000/api/missions/$MID
```

---

### 7.2 Mission start fails — invalid transition

**Symptom:** `POST /api/missions/{id}/start` returns 400.

**Cause:** The mission is not in `PLANNED` state. You need to call `/plan` before `/start`.

**Mission FSM:** PLANNING → (plan) → PLANNED → (start) → ACTIVE

---

### 7.3 Emergency mission abort

```bash
curl -X POST http://localhost:5000/api/missions/{MISSION_ID}/abort \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"reason":"emergency-abort"}'
```

Abort transitions from any non-terminal state (PLANNING, PLANNED, ACTIVE, PAUSED) → ABORTED.

---

### 7.4 Mission resume after pause

```bash
# Pause
curl -X POST http://localhost:5000/api/missions/{ID}/pause -H "Authorization: Bearer $TOKEN"

# Resume when ready
curl -X POST http://localhost:5000/api/missions/{ID}/resume -H "Authorization: Bearer $TOKEN"
```

---

## 8. Authentication Issues

### 8.1 Token expired (401)

Tokens expire after 60 minutes (`MC_V4_JWT_EXPIRE_MINUTES`).

```bash
# Re-login
curl -X POST http://localhost:5000/api/auth/token \
  -d '{"username":"pilot1","password":"pilot1-secret"}'
```

---

### 8.2 Permission denied (403)

| Role | Allowed |
|------|---------|
| ADMIN | All commands on all drones |
| PILOT | Commands on assigned drones only |
| OBSERVER | **No commands** — read-only |

If a PILOT gets 403 on a drone that should be assigned, ask an ADMIN to update the operator's `allowed_drones` list in the operator store.

---

## 9. Monitoring Checklist (Before a Flight)

- [ ] `GET /api/health` → `"status": "ok"`, `"mqtt_connected": true`
- [ ] `GET /api/fleet/health` → target drone shows `GREEN`
- [ ] `GET /api/drones/{id}/preflight` → all checks pass
- [ ] MQTT broker logs: no disconnect events in last 5 min
- [ ] DB: alembic revision matches `alembic current`
- [ ] Simulator running (if SIM mode): `fleet_simulator.py` publishing

---

## 10. Log Locations

| Component | Log command |
|-----------|------------|
| Backend | `docker logs ops-mission-control-v4-1 -f` |
| MQTT broker | `docker logs ops-mqtt-1 -f` |
| PostgreSQL | `docker logs ops-postgres-1 -f` |
| Simulator | Console output of `fleet_simulator.py` |
