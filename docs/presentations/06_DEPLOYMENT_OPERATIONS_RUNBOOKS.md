# Deployment, Operations & Runbooks

**Date:** February 2026  
**Project:** AI-Enabled Drone Fleet Operations  
**Audience:** DevOps, Operations teams, production managers

**Suite Index:** [00_INDEX.md](00_INDEX.md) • **References:** [07_REFERENCES.md](07_REFERENCES.md)

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Production Deployment](#2-production-deployment)
3. [Monitoring & Alerting](#3-monitoring--alerting)
4. [Operational Runbooks](#4-operational-runbooks)
5. [Troubleshooting](#5-troubleshooting)
6. [Disaster Recovery](#6-disaster-recovery)
7. [Security Hardening](#7-security-hardening)
8. [Performance Tuning](#8-performance-tuning)

---

## 1. Quick Start

### 1.1 Local Development Environment

**Prerequisites**:
- Python 3.9+
- Docker & Docker Compose
- Git
- 2GB RAM, 5GB disk space

**Setup (5 minutes)**:

```bash
# Clone repository
git clone https://github.com/nsin08/ai_drones
cd ai_drones

# Install Python dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r poc/requirements.txt

# Start MQTT broker + InfluxDB + Grafana
cd ops
docker compose up -d
cd ..

# Verify services are running
docker compose -f ops/docker-compose.yml ps
# Expected output:
# SERVICE        STATUS      PORTS
# mosquitto      Up 2 min    1883->1883/tcp
# influxdb       Up 1 min    8086->8086/tcp
# grafana        Up 1 min    3000->3000/tcp
# telegraf       Up 1 min    (no exposed ports)

# Launch simulator with 4 drones
cd poc
python fleet_simulator.py --broker localhost --drones 4 --headless
# Expected output:
# [INFO] Starting MQTT client (broker=localhost:1883)
# [INFO] Creating 4 drones
# [INFO] PATROL-01: Connected to MQTT
# [INFO] Fleet simulator running (spawned 4 drone threads)
```

**Open Dashboard**:
- Web UI: http://localhost:5000 (Flask)
- Grafana: http://localhost:3000 (admin/admin)
- MQTT: localhost:1883

### 1.2 Verify Installation

```bash
# Test 1: MQTT connectivity
mosquitto_sub -h localhost -t "fleet/+/telemetry" -v
# Expected: See messages like:
# fleet/PATROL-01/telemetry {"lat": 28.6139, "lon": 77.2090, ...}

# Test 2: InfluxDB connectivity
curl -X POST http://localhost:8086/api/v2/write \
  -H "Authorization: Token mytoken" \
  -d "test,tag=value field=1"
# Expected: HTTP 204 (success)

# Test 3: Flask backend
curl http://localhost:5000/api/status
# Expected: {"status": "ready", "drones": ["PATROL-01", "PATROL-02", ...]}

# Test 4: Run unit tests
pytest poc/tests/unit/ -v
# Expected: All tests pass
```

---

## 2. Production Deployment

### 2.1 Architecture: Single-Site 100-Drone Deployment

**Hardware Requirements**:

| Component | Count | Specs | Cost |
|-----------|-------|-------|------|
| **Compute** | | | |
| Backend Server | 4 | 8-core, 16GB RAM, SSD | $4k |
| Database Server | 2 | 16-core, 64GB RAM, NVMe | $8k |
| WiFi AP | 10 | Enterprise 5GHz, PoE | $3k |
| **Networking** | | | |
| Network Switch | 1 | 48-port PoE, managed | $2k |
| Router | 1 | Dual-WAN, enterprise-grade | $1k |
| Cables/Cabling | 1 | Ethernet, fiber runs | $500 |
| **Monitoring** | | | |
| Monitoring PC | 1 | 4-core, 8GB RAM | $500 |
| **Total** | | | **$19.5k** |

**Network Topology**:

```
Internet
  │
  ▼
┌──────────────┐
│ Firewall     │  (Restrict to needed IPs)
│ (pfsense)    │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Managed Switch (PoE)                 │
│  • Drones auto-power via PoE         │
│  • VLAN 10: Drones (WiFi APs)        │
│  • VLAN 20: Backend (internal only)  │
│  • VLAN 30: Management (restricted)  │
└────┬───────────────────────────────┬─┘
     │                               │
     ▼ VLAN 10                       ▼ VLAN 20
  ┌─────────────────────┐       ┌─────────────────┐
  │ WiFi APs (10 units) │       │ Backend Cluster │
  │  • 5GHz, 802.11ax   │       │  • 4× Flask     │
  │  • 100 Mbps/AP      │       │  • 1× Load Bal  │
  │  • Mesh enabled     │       └────────┬────────┘
  │                     │                │
  │  [100 Drones]       │        ┌───────┴────────┐
  │  1-10 per AP        │        │                │
  └─────────────────────┘   ┌────▼────┐    ┌──────▼───┐
                            │InfluxDB │    │PostgreSQL│
                            │Cluster  │    │Cluster   │
                            └─────────┘    └──────────┘
```

### 2.2 Kubernetes Deployment (Optional, for >500 drones)

**K8s Manifest Example**:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fleet-backend
  namespace: production
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  template:
    metadata:
      labels:
        app: fleet-backend
    spec:
      containers:
      - name: backend
        image: ai_drones:latest
        ports:
        - containerPort: 5000
        env:
        - name: MQTT_BROKER
          value: "mosquitto:1883"
        - name: INFLUXDB_URL
          value: "http://influxdb:8086"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/status
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/ready
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: fleet-backend
  namespace: production
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 5000
  selector:
    app: fleet-backend
---
# hpa.yaml (Auto-scaling)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fleet-backend-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fleet-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Deploy**:
```bash
kubectl apply -f deployment.yaml -f service.yaml -f hpa.yaml
kubectl rollout status deployment/fleet-backend -n production
```

### 2.3 Environment Variables & Secrets

**`.env` file** (production):

```bash
# Core Configuration
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO

# MQTT Configuration
MQTT_BROKER=mosquitto.local
MQTT_PORT=1883
MQTT_KEEPALIVE=60
MQTT_BATCH_SIZE=100  # Buffer messages for efficiency

# Database Configuration
INFLUXDB_URL=http://influxdb.local:8086
INFLUXDB_ORG=ai-drones
INFLUXDB_BUCKET=telemetry
INFLUXDB_RETENTION=2592000  # 30 days

POSTGRES_HOST=postgres.local
POSTGRES_USER=appuser
POSTGRES_DB=fleet_ops
POSTGRES_PORT=5432

# Security
JWT_SECRET=<generate-random-256-bit-key>
API_KEY_DRONE=<generate-random-key>
TLS_CERT_PATH=/etc/ssl/certs/server.crt
TLS_KEY_PATH=/etc/ssl/private/server.key

# Feature Flags
AI_ENABLED=true
ANOMALY_DETECTION=true
PREDICTIVE_MAINTENANCE=false  # Coming in Phase 2
AUTONOMOUS_RTB=true

# Performance
MAX_CONCURRENT_DRONES=100
WEBSOCKET_PING_INTERVAL=30
TELEMETRY_BUFFER_SIZE=1000
```

**Use secrets manager** (AWS Secrets Manager, HashiCorp Vault, etc):

```bash
# Store secrets (never in git)
aws secretsmanager create-secret \
  --name prod/fleet-api-key \
  --secret-string "$(openssl rand -base64 32)"

# Reference in code
import boto3
secrets_client = boto3.client('secretsmanager')
api_key = secrets_client.get_secret_value(SecretId='prod/fleet-api-key')['SecretString']
```

---

## 3. Monitoring & Alerting

### 3.1 Key Metrics to Track

**System Health**:
```
Metric Name              | Threshold | Action
────────────────────────────────────────────────────
MQTT Broker CPU          | >80%      | Page on-call
MQTT Broker Memory       | >85%      | Scale broker cluster
Backend Server CPU       | >90%      | Trigger autoscale
Backend Response Time    | >1000ms   | Investigate query
InfluxDB Write Latency   | >100ms    | Check disk I/O
PostgreSQL Connections   | >200      | Kill idle sessions
```

**Drone Health** (aggregate):
```
Metric Name              | Warning | Critical | Action
────────────────────────────────────────────────────────
Active Drones           | <8      | <5       | Investigate
Avg Battery %           | <50%    | <20%     | Recommend landing
Fault Rate              | >10%    | >25%     | Stop missions
GPS Loss Events         | >3      | >5       | Check interference
```

### 3.2 Grafana Dashboard Setup

**Key Panels**:

```
┌──────────────────────────────────────────────────────┐
│ Fleet Operations Dashboard (Production)              │
├──────────────────────────────────────────────────────┤
│                                                      │
│ ┌─────────────┐ ┌──────────┐ ┌─────────────────┐   │
│ │Active Drones│ │ Avg Battery│ │ Missions Today│   │
│ │  [===] 12   │ │ [===] 75% │ │      5         │   │
│ │  (±2/hour)  │ │ Σ 75%     │ │ 4 completed    │   │
│ └─────────────┘ └──────────┘ └─────────────────┘   │
│                                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │ System Health (30-day)                         │  │
│ │                                                 │  │
│ │ MQTT Broker: ██████████░░░ 92% uptime         │  │
│ │ Backend API: ██████████░░░ 99% uptime         │  │
│ │ InfluxDB:    ██████████░░░ 99.8% uptime       │  │
│ │ PostgreSQL:  ██████████░░░ 99.7% uptime       │  │
│ │                                                 │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │ Response Latency (p50, p95, p99)               │  │
│ │                                                 │  │
│ │ Command (ms):    45    120    250               │  │
│ │ Telemetry (ms):  30    80     150               │  │
│ │ Dashboard (ms): 300   1200    3500              │  │
│ │                                                 │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │ Fleet Status Table (sorted by battery)         │  │
│ │                                                 │  │
│ │ Name        │ Battery │ Mode   │ GPS    │ Faults
│ │ ────────────┼─────────┼────────┼────────┼────────│
│ │ PATROL-03   │  15% ⚠️ │ HOLD   │ ✓  FIX │   1   │
│ │ PATROL-10   │  32%    │ AUTO   │ ✗  ⚠️  │   2   │
│ │ PATROL-01   │  94%    │ AUTO   │ ✓      │   0   │
│ │ ESCORT-02   │  78%    │ LOITER │ ✓      │   0   │
│ │ ...         │  ...    │ ...    │ ...    │  ... │
│ │                                                 │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**Alerting Rules** (Prometheus/Grafana):

```yaml
# alerts.yaml
groups:
  - name: fleet_operations
    rules:
    - alert: HighMQTTLatency
      expr: mqtt_message_latency_p99 > 100
      for: 2m
      annotations:
        summary: "MQTT broker latency {{ $value }}ms"
        runbook: "docs/runbooks/mqtt-latency.md"
        
    - alert: DroneOffline
      expr: drone_online{drone_id=~".*"} == 0
      for: 5m
      annotations:
        summary: "Drone {{ $labels.drone_id }} offline"
        runbook: "docs/runbooks/drone-offline.md"
        
    - alert: LowBatteryFleet
      expr: avg(drone_battery_pct) < 30
      for: 5m
      annotations:
        summary: "Fleet average battery {{ $value }}%"
        action: "Recommend fleet landing"
        
    - alert: DatabaseWriteErrors
      expr: increase(influxdb_write_errors[5m]) > 10
      for: 2m
      annotations:
        summary: "InfluxDB write errors: {{ $value }}/5min"
        runbook: "docs/runbooks/influxdb-troubleshoot.md"
```

---

## 4. Operational Runbooks

### 4.1 Runbook: Adding a New Drone to Fleet

**Scenario**: Hardware team has assembled a new drone and wants to join it to operations

**Pre-flight Checklist**:
- [ ] Frame assembled and balanced
- [ ] Motors/ESCs calibrated
- [ ] Propellers installed (marked CW/CCW correctly)
- [ ] Battery charged (test with load)
- [ ] Flight controller flashed with latest ArduPilot (v4.4+)
- [ ] Companion computer (RPi4) flashed with Ubuntu 22.04 + Python 3.11
- [ ] WiFi adapter configured (5GHz preferred, antenna oriented vertically)

**Steps**:

```bash
# Step 1: SSH to companion computer (RPi4)
ssh pi@patrol-13.local  # (or use IP address)
# Default password: raspberry (change ASAP!)

# Step 2: Clone & install software
cd /home/pi
git clone https://github.com/nsin08/ai_drones
cd ai_drones/poc
pip install -r requirements.txt
pip install systemd  # For daemon management

# Step 3: Configure drone identity
cat > /etc/drone_config.json << EOF
{
  "drone_id": "PATROL-13",
  "mission_role": "WINGMAN",
  "mqtt_broker": "mission-control.local",
  "mqtt_port": 1883,
  "mavlink_port": "/dev/ttyUSB0",
  "telemetry_rate_hz": 2,
  "max_battery_percent": 100,
  "min_battery_percent": 10
}
EOF

# Step 4: Validate MAVLink connection to flight controller
# Via serial connection:
mavproxy.py --master=/dev/ttyUSB0 --baudrate=115200
# Expected: HEARTBEAT messages from flight controller
# Type: QUADROTOR
# Version: ArduCopter v4.4.x

# Step 5: Test MQTT connectivity
python3 -c "
import paho.mqtt.client as mqtt
client = mqtt.Client()
client.connect('mission-control.local', 1883, 60)
client.publish('fleet/PATROL-13/ping', 'hello')
print('MQTT connected successfully')
"

# Step 6: Run integration test
pytest ../poc/tests/integration/test_mqtt_adapter.py::test_drone_connection -v
# Expected: test_drone_connection PASSED

# Step 7: Install as systemd service (auto-start on boot)
sudo tee /etc/systemd/system/drone-telemetry.service << EOF
[Unit]
Description=Drone Telemetry Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/ai_drones/poc
ExecStart=/usr/bin/python3 /home/pi/ai_drones/poc/mission_simulator.py \
  --broker mission-control.local \
  --drone-id PATROL-13 \
  --no-simulator
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable drone-telemetry
sudo systemctl start drone-telemetry

# Step 8: Verify service is running
sudo systemctl status drone-telemetry
# Expected: "● drone-telemetry.service - Drone Telemetry Service
#              Loaded: loaded (/etc/systemd/system/drone-telemetry.service)
#              Active: active (running)"

# Step 9: Check telemetry in Grafana
# Visit http://mission-control:3000
# Navigate to "Fleet Status" dashboard
# Look for "PATROL-13" row with green ✓ indicators

# Step 10: Authorize in mission control
# Via backend API:
curl -X POST http://mission-control:5000/api/drones/authorize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "drone_id": "PATROL-13",
    "max_drones_per_mission": 50,
    "allowed_missions": ["PATROL", "ESCORT"]
  }'
# Expected: {"status": "authorized", "drone_id": "PATROL-13"}

# Step 11: Perform first flight
# (See "First Flight Checklist" runbook)

# Troubleshooting:
# Q: "MQTT connection refused"
#    A: Check network connectivity: ping mission-control.local
#       Check firewall rules: sudo ufw status
#
# Q: "MAVLink HEARTBEAT not received"
#    A: Check serial connection: ls -la /dev/ttyUSB*
#       Verify baud rate: 115200 (ArduPilot default)
#
# Q: "Service fails to start"
#    A: Check logs: sudo journalctl -u drone-telemetry -f
```

### 4.2 Runbook: Emergency Fleet Landing

**Scenario**: Weather deteriorates rapidly, need to land all drones immediately

**Activation Criteria**:
- Sustained wind >25 knots
- Rain/lightning detected within 5km
- Operator manually triggered

**Procedure** (takes 3 minutes):

```bash
# PHASE 1: Initiate Landing (10 seconds)
# Option A: Via Web Dashboard
#   1. Click "EMERGENCY STOP" button (red)
#   2. Select "LAND ALL" option
#   3. Confirm dialog: "This cannot be undone"
#   4. Watch status board transition to "LANDING"

# Option B: Via API (for automated triggers)
curl -X POST http://mission-control:5000/api/missions/emergency-stop \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "LAND_ALL", "reason": "Weather deterioration"}'

# PHASE 2: Monitor Landing (2-3 minutes)
# Expected sequence per drone:
#   1. Mode: LAND
#   2. Descent rate: 1-2 m/s
#   3. Status: "Landing..."
#   4. Time to ground: Varies (50-120m altitude)

# PHASE 3: Verify Safe (post-landing)
# Check Grafana dashboard:
#   ✓ All drones showing "Landed"
#   ✓ All motors DISARMED
#   ✓ GPS still locked (no drift during descent)

# Logging:
# Check backend logs for emergency event:
tail -f /var/log/fleet-ops/backend.log | grep "EMERGENCY"
# Expected: 
#   [2026-02-01 14:32:15] EMERGENCY_STOP initiated
#   [2026-02-01 14:32:45] PATROL-01 landed (took 30s)
#   [2026-02-01 14:33:12] PATROL-12 landed (took 57s)
#   [2026-02-01 14:34:18] All drones landed (total 3m18s)

# Recovery (when conditions improve):
# 1. Check weather: wind <15 knots, no precipitation
# 2. Inspect drones for damage
# 3. Restart fleet: via dashboard "Resume Operations"
```

### 4.3 Runbook: Database Backup & Recovery

**Frequency**: Daily at 02:00 UTC

**Backup**:

```bash
#!/bin/bash
# backup.sh (runs daily via cron)

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/mnt/backups/fleet-ops"
RETENTION_DAYS=30

# Backup InfluxDB
influx backup ${BACKUP_DIR}/influxdb_${DATE} \
  --host http://influxdb:8086 \
  --token $INFLUXDB_TOKEN

# Backup PostgreSQL
pg_dump \
  -h postgres.local \
  -U appuser \
  -d fleet_ops \
  -F custom \
  -f ${BACKUP_DIR}/postgres_${DATE}.dump

# Backup file storage (MAVLink logs, images)
rsync -av \
  /var/lib/fleet-ops/files/ \
  ${BACKUP_DIR}/files_${DATE}/ \
  --delete

# Compress
tar -czf ${BACKUP_DIR}/backup_${DATE}.tar.gz \
  ${BACKUP_DIR}/influxdb_${DATE} \
  ${BACKUP_DIR}/postgres_${DATE}.dump \
  ${BACKUP_DIR}/files_${DATE}

# Cleanup old backups (older than 30 days)
find ${BACKUP_DIR} -name "backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

# Verify backup integrity
tar -tzf ${BACKUP_DIR}/backup_${DATE}.tar.gz > /dev/null && \
  echo "Backup ${DATE} verified successfully" || \
  echo "ERROR: Backup verification failed!" && exit 1

# Upload to cloud storage (AWS S3)
aws s3 cp ${BACKUP_DIR}/backup_${DATE}.tar.gz \
  s3://fleet-ops-backups/daily/${DATE}/ \
  --sse AES256 \
  --storage-class GLACIER

echo "Backup completed: $(du -h ${BACKUP_DIR}/backup_${DATE}.tar.gz | cut -f1)"
```

**Recovery** (if data loss):

```bash
# Step 1: Stop all services
docker compose -f ops/docker-compose.yml stop

# Step 2: Restore from backup
RESTORE_DATE="20260201_020000"
BACKUP_FILE="/mnt/backups/fleet-ops/backup_${RESTORE_DATE}.tar.gz"

# Extract backup
tar -xzf ${BACKUP_FILE} -C /tmp

# Restore InfluxDB
influx restore /tmp/backup_${RESTORE_DATE}/influxdb_${RESTORE_DATE} \
  --host http://influxdb:8086 \
  --token $INFLUXDB_TOKEN

# Restore PostgreSQL
pg_restore \
  -h postgres.local \
  -U appuser \
  -d fleet_ops \
  -c \
  /tmp/backup_${RESTORE_DATE}/postgres_${RESTORE_DATE}.dump

# Restore file storage
rsync -av \
  /tmp/backup_${RESTORE_DATE}/files_${RESTORE_DATE}/ \
  /var/lib/fleet-ops/files/ \
  --delete

# Step 3: Restart services
docker compose -f ops/docker-compose.yml up -d

# Step 4: Verify recovery
curl http://mission-control:5000/api/status
# Expected: {"status": "ready", "drones": [...], "last_backup": "2026-02-01T02:00:00Z"}

echo "Recovery completed. Data restored to ${RESTORE_DATE}."
```

---

## 5. Troubleshooting

### 5.1 Common Issues & Solutions

**Issue: Drone not connecting to MQTT**

```
Symptom: Dashboard shows drone "OFFLINE"
Logs: [ERROR] Connection timeout (>10s)

Diagnosis:
1. Check network: ping drone.local
2. Check MQTT broker: docker logs mosquitto
3. Check firewall: sudo iptables -L | grep 1883
4. Check drone companion computer: ssh pi@drone.local

Solution:
- Verify broker address in /etc/drone_config.json
- Check WiFi signal strength: ssh pi@drone.local && iwconfig
- Restart MQTT client on drone: systemctl restart drone-telemetry
- If DNS issue: use IP address instead of hostname
```

**Issue: High telemetry latency (>500ms)**

```
Symptom: Dashboard updates slowly, commands lag
Metrics: telegraf_latency_p99 > 1000ms

Diagnosis:
1. Check MQTT load: docker exec mosquitto mosquitto_info
2. Check network latency: ping -c 10 drone.local | tail -1
3. Check InfluxDB write latency: grafana_influx_write_time_p99
4. Check backend server load: top

Solution:
- Scale MQTT broker: deploy EMQX cluster (3+ nodes)
- Reduce telemetry frequency: {"telemetry_rate_hz": 1} (if acceptable)
- Compress messages: Enable gzip compression in Telegraf config
- Upgrade network: Check WiFi AP channel utilization (use non-overlapping channels)
```

**Issue: Drones losing GPS lock mid-flight**

```
Symptom: Drone altitude/position frozen, GPS quality indicator red
Logs: [WARN] GPS_SIGNAL_LOST (HDOP > 5.0)

Diagnosis:
1. Check for RF interference: sudo iwlist wlan0 scan | grep Frequency
2. Check antenna position: Should be vertical, not tilted
3. Check for obstructions: Trees, buildings, metal structures nearby
4. Check GPS satellite count: Telemetry > gps_num_sats

Solution:
- Reorient antenna (vertical orientation preferred)
- Move WiFi AP away from GPS antenna (interference on 2.4GHz)
- Move flight area away from obstructions
- Wait for better GPS constellation (if HDOP > 3, wait 2-5 minutes)
- Upgrade to ublox F9P module (better multipath rejection)
```

---

## 6. Disaster Recovery

### 6.1 RTO & RPO Targets

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Single server failure | 15 min | <5 min | Auto-failover to standby |
| Data loss | 1 hour | 1 day | Restore from S3 backup |
| Ransomware attack | 4 hours | 24 hours | Full restore to air-gapped backup |
| Regional outage | 2 hours | 1 day | Failover to secondary region |

### 6.2 Backup Strategy

```
Daily Backup Schedule:
  02:00 UTC: Full backup (InfluxDB + PostgreSQL + files)
             → Compress → Upload to AWS S3 Glacier
  
  Weekly: Full restore test (every Sunday 03:00 UTC)
          → Verify backup integrity
          → Ensure recovery procedure works
  
  Monthly: Disaster recovery drill
           → Simulate complete data loss
           → Time full recovery
           → Document any gaps

Retention:
  Daily:   Last 7 days (storage: 7GB)
  Weekly:  Last 4 weeks (storage: 16GB)
  Monthly: Last 12 months (storage: 120GB)
  Total:   ~150GB (AWS S3 Glacier = $3/month)
```

---

## 7. Security Hardening

### 7.1 Network Security

**Firewall Rules** (Production):

```
Zone: DMZ (External-facing)
  Ingress:
    - TCP 80 (HTTP redirect to 443)
    - TCP 443 (HTTPS/TLS)
    From: Anywhere (0.0.0.0/0)
  
Zone: Internal (Backend)
  Ingress:
    - TCP 1883 (MQTT)
    From: Drones only (10.0.1.0/24)
    
    - TCP 5432 (PostgreSQL)
    From: Backend servers only (10.0.2.0/24)
    
    - TCP 8086 (InfluxDB)
    From: Backend servers & Telegraf only (10.0.2.0/24, 10.0.3.0/24)
  
Zone: Management
  Ingress:
    - TCP 22 (SSH)
    From: VPN/Admin IPs only (whitelist)
    
    - TCP 3000 (Grafana)
    From: VPN only (10.255.0.0/16)

Deny All (default)
```

### 7.2 TLS/Encryption

```bash
# Generate self-signed certificate for development
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365 \
  -subj "/CN=mission-control.local"

# In production, use Let's Encrypt (free, auto-renew)
sudo certbot certonly --standalone \
  -d mission-control.yourdomain.com \
  --agree-tos -n

# Configure nginx to require TLS 1.2+
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;
```

### 7.3 Authentication & Authorization

```python
# Backend API authentication (JWT tokens)
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

jwt = JWTManager(app)

@app.route('/api/login', methods=['POST'])
def login():
    """Issue JWT token for API access"""
    username = request.json.get('username')
    password = request.json.get('password')
    
    # Verify against database (bcrypt hashed)
    user = db.session.query(User).filter_by(username=username).first()
    if not user or not verify_password(password, user.password_hash):
        return {"error": "Invalid credentials"}, 401
    
    # Issue token (expires in 1 hour)
    access_token = create_access_token(
        identity=user.id,
        expires_delta=timedelta(hours=1)
    )
    return {"access_token": access_token}

@app.route('/api/drones', methods=['GET'])
@jwt_required()
def list_drones():
    """Requires valid JWT token"""
    user_id = get_jwt_identity()
    drones = db.session.query(Drone).filter_by(owner_id=user_id).all()
    return jsonify([d.to_dict() for d in drones])
```

---

## 8. Performance Tuning

### 8.1 Optimization Checklist

**MQTT Broker**:
- [ ] Tune `max_connections` = 150 (drones + servers + monitoring)
- [ ] Enable `max_inflight_messages` = 20 (batch writes)
- [ ] Configure `max_queued_messages` = 1000
- [ ] Monitor: `mosquitto_pub -t '$SYS/broker/load/messages/sent' -v`

**InfluxDB**:
- [ ] Set `retention policy` = 7 days raw, 90 days downsampled
- [ ] Enable `wal` (write-ahead log) for durability
- [ ] Configure `cache_size` = 25% of available RAM
- [ ] Use `batch writes` (100+ points per request)
- [ ] Query optimization: Always use tag filters, avoid regex

**PostgreSQL**:
- [ ] Set `shared_buffers` = 25% of RAM
- [ ] Configure `effective_cache_size` = 50-75% of RAM
- [ ] Index on frequently queried columns: `drone_id`, `timestamp`
- [ ] Vacuum daily: `VACUUM ANALYZE;`
- [ ] Monitor: `pg_stat_statements` extension

**Backend (Flask)**:
- [ ] Enable gzip compression: `Content-Encoding: gzip`
- [ ] Use connection pooling: `SQLAlchemy pool_size=20`
- [ ] Cache frequent queries: Redis (optional)
- [ ] Profile code: Use `py-spy` to find bottlenecks

### 8.2 Load Testing

```bash
# Simulate 100 concurrent drones (stress test)
python poc/tests/load/simulate_fleet.py \
  --drones 100 \
  --duration 600 \
  --telemetry-rate 2 \
  --broker mission-control.local

# Expected results (production hardware):
# - Latency p99: <200ms
# - CPU usage: <70%
# - Memory: <80%
# - No packet loss
```

---

**Document maintained by @nsin08**  
**Last updated: February 2026**  
**Repository**: https://github.com/nsin08/ai_drones
