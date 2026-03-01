# Hardware-Only Docker Compose

## Quick Start

**Minimal mode (MQTT + Mission Control only):**
```bash
cd ops
docker compose -f docker-compose.hardware.yml up -d
```

**With monitoring (add Grafana dashboard):**
```bash
# Uncomment influxdb, grafana, telegraf sections in docker-compose.hardware.yml
docker compose -f docker-compose.hardware.yml up -d
```

---

## Service Breakdown

### ✅ Essential Services (Always Included)

#### 1. **mosquitto** (MQTT Broker)
- **Port:** 1883 (MQTT), 9001 (WebSocket)
- **Used by:**
  - `drone_gateway.py` — publishes real hardware telemetry to `fleet/<droneId>/telemetry`
  - `mission_control_v3.py` — subscribes to telemetry topic
- **Can disable?** NO — core messaging hub

#### 2. **mission-control** (Web UI Backend)
- **Port:** 5000
- **Serves:**
  - React UI (Fleet Roster, Mission Setup, etc.)
  - MQTT subscriptions (displays live drone data)
- **Can disable?** NO — shows the UI

---

### ⚠️ Optional Services (Monitoring Stack)

#### **influxdb** (Time-Series Database)
- Stores historical telemetry
- Only needed if you want long-term metrics
- Can be added later if needed

#### **grafana** (Dashboard)
- Visualizes metrics from influxdb
- Only useful with influxdb enabled
- Not needed for basic UI operation

#### **telegraf** (Metrics Collector)
- Bridges MQTT → influxdb
- Only needed if using influxdb/grafana

---

### ❌ Removed (Not Needed for Hardware)

**swarmsim** — Fleet simulator (use real hardware instead)  
**drone (SITL)** — ArduPilot simulator (use real hardware instead)  
**inventory** — Auto-discovery service (you know your COM ports)

---

## Workflow

### Setup (Once)
```bash
cd ops
docker compose -f docker-compose.hardware.yml up -d
```

### Start Hardware Gateway (in separate terminal)
```bash
cd poc2
.\.venv\Scripts\activate
python drone_gateway.py --port COM6 --drone-id HW-001
# Or for multi-drone:
# python drone_gateway.py --ports COM6:HW-001,COM3:HW-002
```

### View UI
- **Mission Control:** http://localhost:5000

---

## Switching Modes

**From full stack back to hardware-only:**
```bash
# Stop current stack
docker compose down

# Start hardware-only
docker compose -f docker-compose.hardware.yml up -d
```

**Add monitoring later:**
```bash
# Edit docker-compose.hardware.yml → uncomment influxdb/grafana/telegraf sections
docker compose -f docker-compose.hardware.yml up -d
```

---

## Troubleshooting

**"MQTT connection refused"**
- Ensure mosquitto is running: `docker ps | grep mosquitto-broker`
- Port 1883 should be open

**"Cannot connect to Docker daemon"**
- Ensure Docker Desktop is running (Windows/Mac)

**"influxdb URL not found"**
- Mock URL in mission-control environment is `http://localhost:8001` (no-op)
- Only needed if actually using influxdb

---

## Ports

| Service | Port | Purpose |
|---------|------|---------|
| mosquitto | 1883 | MQTT broker |
| mission-control | 5000 | Web UI |
| influxdb | 8086 | Metrics API (optional) |
| grafana | 3000 | Dashboard (optional) |
