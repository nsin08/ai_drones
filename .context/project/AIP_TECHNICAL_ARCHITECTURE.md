# AIP Technical Architecture
## Enterprise-Scale Autonomous Intelligence Platform

**Document Version:** 1.2 (Target Architecture Reference)  
**Last Updated:** February 9, 2026  
**Status:** Production Target State (Not Fully Implemented)

> **Context:** This document describes the **target production architecture** for scaling to 1000+ drones with <200ms latency and 99.9% uptime. As of Feb 2026, the validated PoC has hexagonal architecture, 5 fault models, fleet simulator, mission control FSM, React UI, and Docker infrastructure (7 services). See [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) for current capabilities and [AIP_GAP_ANALYSIS.md](AIP_GAP_ANALYSIS.md) for production roadmap.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Component Architecture](#component-architecture)
4. [Data Flow Architecture](#data-flow-architecture)
5. [Scalability & Performance](#scalability--performance)
6. [High Availability & Fault Tolerance](#high-availability--fault-tolerance)
7. [Security Architecture](#security-architecture)
8. [Deployment Topologies](#deployment-topologies)
9. [Technology Stack](#technology-stack)
10. [Integration Interfaces](#integration-interfaces)

---

## System Overview

### Architecture Vision

The AIP platform is designed as a **distributed, event-driven, microservices-based system** that scales from 20 to 1000+ autonomous vehicles while maintaining sub-200ms decision latency. The architecture follows a **hybrid edge-cloud model** where time-critical operations execute at the edge (on drones or field servers) while analytics and long-term intelligence reside in the cloud.

### Design Philosophy

1. **Edge-First Processing** - All mission-critical decisions made without cloud dependency
2. **Eventual Consistency** - Accept temporary divergence for availability
3. **Graceful Degradation** - Partial functionality better than total failure
4. **Observable by Default** - Comprehensive telemetry, logging, and tracing
5. **Security in Depth** - Multiple layers of defense, zero-trust networking

---

## Architecture Principles

### 1. Hexagonal (Ports & Adapters) Architecture

**Purpose:** Decouple business logic from infrastructure concerns

```
┌─────────────────────────────────────────────────────┐
│                  DOMAIN CORE                        │
│  ┌──────────────────────────────────────────────┐  │
│  │  Mission Planner │ Fault Detector │ AI Engine│  │
│  │  Pure Python, No External Dependencies       │  │
│  └──────────────────────────────────────────────┘  │
│                       ↑                              │
│                    (Ports)                           │
│                       ↓                              │
│  ┌──────────────────────────────────────────────┐  │
│  │          ADAPTERS (Implementations)          │  │
│  │  MQTT | REST | gRPC | MAVLink | WebSocket   │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Benefits:**
- Swap MQTT for ROS2/DDS without changing core logic
- Unit test business logic without Docker/MQTT broker
- Support multiple GCS protocols simultaneously

### 2. Event-Driven Architecture

**Purpose:** Decouple producers from consumers, enable asynchronous processing

**Event Categories:**
- **Telemetry Events** - Drone state updates (1-10 Hz)
- **Command Events** - Mission directives, configuration changes
- **Fault Events** - Anomaly detection, health degradation
- **AI Events** - Recommendations, predictions, insights

**Event Backbone:** MQTT (dev/small scale) → EMQX Cluster (production)

### 3. CQRS (Command Query Responsibility Segregation)

**Purpose:** Separate read-heavy analytics from write-heavy telemetry ingestion

```
┌─────────────┐      Write Path (Telemetry Ingestion)
│   Drones    │ ────────────────────────────────────┐
└─────────────┘                                      ↓
                                           ┌──────────────────┐
                                           │  InfluxDB (TSDB) │
                                           │  Write-Optimized │
                                           └────────┬─────────┘
                                                    │
                                          (async replication)
                                                    ↓
┌─────────────┐      Read Path (Dashboards)  ┌─────────────┐
│  Operators  │ ←───────────────────────────│  PostgreSQL  │
└─────────────┘                             │ Read-Optimized│
                                            └───────────────┘
```

### 4. Microservices with Domain-Driven Design

**Service Boundaries:**

| Service | Responsibility | Bounded Context |
|---------|---------------|-----------------|
| **Fleet Registry** | Drone inventory, capabilities, status | Fleet Management |
| **Mission Planner** | Route generation, task allocation | Mission Orchestration |
| **Telemetry Processor** | Stream processing, aggregation | Data Ingestion |
| **Fault Detector** | Anomaly detection, health monitoring | Diagnostics |
| **AI Recommender** | Predictive analytics, decision support | Intelligence |
| **Command Executor** | MAVLink bridge, command lifecycle | Execution |
| **Auth Service** | Authentication, authorization, audit | Security |

---

## Component Architecture

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           OPERATOR LAYER                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                     │
│  │  Web UI    │  │  Mobile    │  │  Mission   │                     │
│  │  Dashboard │  │  App       │  │  Planner   │                     │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘                     │
│         │               │               │                           │
│         └───────────────┴───────────────┘                           │
│                         │                                           │
│                    (HTTPS/WSS)                                      │
│                         ↓                                           │
├─────────────────────────────────────────────────────────────────────┤
│                      API GATEWAY LAYER                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  NGINX / Kong - Load Balancing, Rate Limiting, Auth          │   │
│  └─────────────────────────┬────────────────────────────────────┘   │
│                            │                                        │
├────────────────────────────┼────────────────────────────────────────┤
│                   CONTROL PLANE (Kubernetes)                        │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │
│  │ Mission Control │  │  Fleet Manager │  │  AI Engine     │        │
│  │  Service (Flask)│  │  Service       │  │  Service       │        │
│  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘         │
│           │                   │                   │                 │
│           └───────────────────┴───────────────────┘                 │
│                               │                                     │
│                       (MQTT Publish/Subscribe)                      │
│                               ↓                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │          MQTT Broker Cluster (EMQX)                          │   │
│  │  - Topic-based routing                                       │   │
│  │  - QoS 0/1/2 support                                         │   │
│  │  - Retained messages for state                               │   │
│  │  - Bridge to cloud/edge brokers                              │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                         │
├───────────────────────────┼─────────────────────────────────────────┤
│                    DATA PLANE                                       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │
│  │  InfluxDB     │  │  PostgreSQL   │  │  Redis        │            │
│  │  (Telemetry)  │  │  (Missions)   │  │  (Cache)      │            │
│  └───────────────┘  └───────────────┘  └───────────────┘            │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                    MONITORING & OBSERVABILITY                       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │
│  │  Prometheus   │  │  Grafana      │  │  Jaeger       │            │
│  │  (Metrics)    │  │  (Dashboards) │  │  (Tracing)    │            │
│  └───────────────┘  └───────────────┘  └───────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
                               │
                      (4G/5G/Radio Links)
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        EDGE LAYER (Drones)                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Drone 1..N                                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │   │
│  │  │ ArduPilot   │  │ Companion   │  │  Edge AI    │           │   │
│  │  │ Flight Ctrl │  │ Computer    │  │  (Jetson)   │           │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘           │   │
│  │         │ (MAVLink)      │ (MQTT)         │ (Inference)      │   │
│  │         └────────────────┴────────────────┘                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Services Deep Dive

#### 1. Mission Control Service

**Technology:** Flask + Flask-SocketIO (Python 3.11)  
**Scale:** 1-3 instances (stateless, load-balanced)  
**Responsibility:**
- Mission FSM (IDLE → PLANNING → ACTIVE → COMPLETED)
- Command lifecycle tracking (REQUESTED → SENT → ACK/TIMEOUT)
- Leader reassignment and formation management
- Real-time state broadcast via WebSocket

**APIs:**
- `POST /api/mission/assign` - Assign drones to mission
- `POST /api/mission/plan` - Generate mission plan
- `POST /api/mission/start` - Execute mission
- `GET /api/state/snapshot` - Full state for reconnect recovery
- `WS /socket.io` - Real-time bidirectional updates

**State Storage:** Redis (ephemeral), PostgreSQL (durable)

#### 2. Fleet Manager Service

**Technology:** Go (high-performance concurrency)  
**Scale:** 2-5 instances (HA cluster)  
**Responsibility:**
- Drone inventory and capability registry
- Heartbeat monitoring (stale detection)
- Role assignment and group management
- Firmware version tracking

**Data Model:**
```sql
CREATE TABLE drones (
    id VARCHAR(20) PRIMARY KEY,  -- SIM-001, SITL-042, HW-099
    namespace VARCHAR(10),        -- SIM, SITL, HW
    capabilities JSONB,           -- payload types, flight time, etc.
    last_heartbeat TIMESTAMP,
    firmware_version VARCHAR(50),
    current_mission_id UUID,
    current_role VARCHAR(20)      -- LEADER, WINGMAN, SCOUT, etc.
);
```

#### 3. Telemetry Processor Service

**Technology:** Apache Kafka Streams (Java) or Flink (Scala)  
**Scale:** 3-10 instances (partitioned by drone ID)  
**Responsibility:**
- High-throughput telemetry ingestion (10,000+ msg/sec)
- Stream aggregation (windowed averages, anomaly detection)
- Data enrichment (add weather, terrain data)
- Downsampling for long-term storage

**Processing Pipeline:**
```
MQTT Topic: fleet/{id}/telemetry (raw, 10 Hz)
    ↓
[Kafka Topic: telemetry-raw]
    ↓
[Stream Processor: Aggregate 10 Hz → 1 Hz]
    ↓
[Kafka Topic: telemetry-aggregated]
    ↓
[Sink Connector: Write to InfluxDB]
```

#### 4. AI Recommender Service

**Technology:** Python (FastAPI) + TensorFlow Serving  
**Scale:** 2-5 instances (GPU-accelerated)  
**Responsibility:**
- Fault prediction (battery, GPS, motors)
- Anomaly detection (drift from expected behavior)
- Route optimization recommendations
- Risk scoring for mission viability

**ML Models:**
- **Battery SoC Estimator** - LSTM, trained on 10K flight hours
- **Failure Predictor** - Random Forest, 95% precision
- **Path Optimizer** - A* with learned cost function
- **Formation Optimizer** - Reinforcement Learning (PPO)

**Inference Latency:** <50ms (95th percentile)

#### 5. Command Executor Service

**Technology:** Python (asyncio) + pymavlink  
**Scale:** 1 instance per MAVLink connection pool  
**Responsibility:**
- MAVLink ↔ MQTT protocol bridge
- Command validation and safety checks
- Acknowledgment tracking with timeout
- Audit logging for compliance

**Command Flow:**
```
Operator → [API] → [MQTT: fleet/{id}/command] → [Executor]
                                                      ↓
                                            [MAVLink: COMMAND_LONG]
                                                      ↓
                                                  ArduPilot
                                                      ↓
                                            [MAVLink: COMMAND_ACK]
                                                      ↓
                           [MQTT: fleet/system/command_ack] ← [Executor]
```

---

## Data Flow Architecture

### Telemetry Flow (Typical 1-Second Cycle)

```
T=0.000s  Drone: GPS fix, IMU read, battery voltage sample
T=0.010s  ArduPilot: Pack into HEARTBEAT, GLOBAL_POSITION_INT, SYS_STATUS
T=0.020s  MAVLink: Serialize and transmit over 4G
T=0.050s  Command Executor: Receive MAVLink, convert to JSON
T=0.060s  MQTT Publish: fleet/HW-042/telemetry
T=0.070s  MQTT Broker: Fanout to subscribers (Mission Control, Telemetry Processor, AI)
T=0.080s  Mission Control: Update in-memory state, check formation
T=0.090s  Telemetry Processor: Append to Kafka topic
T=0.100s  AI Recommender: Run inference on latest window
T=0.120s  WebSocket: Broadcast to connected operators
T=0.130s  Operator Dashboard: Update map marker and telemetry panel

Total Latency: 130ms (well under 200ms budget)
```

### Command Flow (Mission Start Example)

```
T=0.000s  Operator: Click "Start Mission" button
T=0.010s  Web UI: POST /api/mission/start
T=0.020s  Mission Control: Transition FSM to ACTIVE
T=0.030s  Mission Control: Publish UPLOAD_MISSION to fleet/D001/command
T=0.040s  MQTT Broker: Route to Command Executor
T=0.050s  Command Executor: Convert to MAVLink MISSION_ITEM_INT
T=0.060s  MAVLink: Transmit to drone
T=0.100s  ArduPilot: Process mission, send MISSION_ACK
T=0.140s  Command Executor: Receive ACK, publish to fleet/system/command_ack
T=0.150s  Mission Control: Mark command as ACKED
T=0.160s  WebSocket: Broadcast state update to operator
T=0.170s  Operator Dashboard: Show "Mission Uploaded" status

Total Latency: 170ms (within budget)
```

---

## Scalability & Performance

### Scaling Dimensions

| Dimension | Current (MVP) | Target (Production) | Strategy |
|-----------|---------------|---------------------|----------|
| **Concurrent Drones** | 20 | 1000 | Horizontal scaling of all services |
| **Telemetry Rate** | 1 Hz | 10 Hz | Stream processing, downsampling |
| **Mission Throughput** | 10/min | 100/min | Stateless services, Redis caching |
| **Operator Concurrency** | 5 | 100 | WebSocket fanout, CDN for static assets |
| **Data Retention** | 7 days | 1 year | Tiered storage (hot/warm/cold) |

### Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Command Latency (P50)** | <100ms | Cloud → Drone → ACK |
| **Command Latency (P99)** | <200ms | End-to-end with retries |
| **Telemetry Latency (P95)** | <150ms | Drone → Dashboard update |
| **Dashboard Load Time** | <2s | First contentful paint |
| **API Response Time (P95)** | <500ms | All REST endpoints |
| **WebSocket Event Latency** | <50ms | Server → client broadcast |
| **MQTT Throughput** | 50K msg/sec | Peak load capacity |
| **Database Write Throughput** | 100K points/sec | InfluxDB telemetry ingestion |

### Horizontal Scaling Strategy

#### MQTT Broker Cluster (EMQX)

```
┌────────────┐    ┌────────────┐    ┌────────────┐
│ EMQX Node1 │←──→│ EMQX Node2 │←──→│ EMQX Node3 │
└────────────┘    └────────────┘    └────────────┘
      ↑                 ↑                 ↑
      │                 │                 │
  (Load Balancer - Round Robin DNS)
      │                 │                 │
      ↓                 ↓                 ↓
   Drones          Services          Operators
  (300-350)       (50-100)            (10-50)
```

**Cluster Configuration:**
- 3-node cluster for HA (quorum-based leader election)
- Shared subscription groups for load distribution
- Sticky sessions for stateful clients
- Auto-scaling based on connection count

#### Kubernetes Service Scaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mission-control-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mission-control
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: websocket_connections
      target:
        type: AverageValue
        averageValue: "500"
```

---

## High Availability & Fault Tolerance

### HA Design Patterns

#### 1. Stateless Services with External State

**All application services are stateless:**
- Session state in Redis (replicated)
- Mission state in PostgreSQL (HA cluster)
- Telemetry in InfluxDB (clustered)

**Benefits:**
- Any service instance can handle any request
- Rolling updates with zero downtime
- Instant failover to healthy replicas

#### 2. Circuit Breaker Pattern

**Implementation:** Resilience4j (Java), Hystrix (legacy), pybreaker (Python)

```python
from pybreaker import CircuitBreaker

mqtt_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    timeout_duration=30,  # Stay open for 30 seconds
    expected_exception=ConnectionError
)

@mqtt_breaker
def publish_command(topic, payload):
    mqtt_client.publish(topic, payload)
```

**Failure Modes:**
- MQTT broker unreachable → Queue commands locally, retry
- Database write failure → Log to disk, async replay
- AI service timeout → Fallback to rule-based logic

#### 3. Bulkhead Isolation

**Purpose:** Prevent cascading failures by isolating resource pools

```
┌─────────────────────────────────────────────────┐
│  Thread Pool 1: Telemetry Processing (80%)      │
├─────────────────────────────────────────────────┤
│  Thread Pool 2: Command Execution (15%)         │
├─────────────────────────────────────────────────┤
│  Thread Pool 3: Admin/API Requests (5%)         │
└─────────────────────────────────────────────────┘
```

If telemetry processing overloads, admin APIs remain responsive.

#### 4. Active-Active Multi-Region (Optional)

**For SaaS deployments:**

```
┌─────────────┐                    ┌─────────────┐
│  US-EAST-1  │←──(Global LB)───→  │  US-WEST-2  │
│  Full Stack │                    │  Full Stack │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       └──────────(Database Replication)──┘
              (PostgreSQL streaming, InfluxDB sync)
```

**Failover Time:** <30 seconds (DNS TTL + health check)

---

## Security Architecture

### Security Layers

#### 1. Network Security

**Perimeter:**
- WAF (Web Application Firewall) for HTTP/HTTPS traffic
- DDoS protection (Cloudflare, AWS Shield)
- VPN for operator access (WireGuard, OpenVPN)
- mTLS for drone-to-cloud communication

**Internal:**
- Network segmentation (VLANs, Kubernetes network policies)
- Zero-trust: Every service authenticates every request
- Encrypted MQTT (TLS 1.3)

#### 2. Authentication & Authorization

**Operator Authentication:**
- OAuth 2.0 / OIDC (Keycloak, Auth0)
- MFA required for production environments
- SSO integration (SAML, LDAP)

**Drone Authentication:**
- Per-drone client certificates (x.509)
- Certificate rotation every 90 days
- Revocation list (CRL) for compromised drones

**MQTT ACLs (Access Control Lists):**
```
# Drone HW-042 can only:
- Publish: fleet/HW-042/*
- Subscribe: fleet/HW-042/command, fleet/system/broadcast

# Mission Control Service can:
- Publish: fleet/+/command, fleet/system/*
- Subscribe: fleet/+/telemetry, fleet/+/events
```

#### 3. Data Encryption

**At Rest:**
- Database encryption (AES-256, transparent)
- Disk encryption (LUKS, BitLocker)
- Secret management (HashiCorp Vault, AWS Secrets Manager)

**In Transit:**
- TLS 1.3 for all HTTP/WebSocket connections
- MQTT over TLS (port 8883)
- MAVLink encryption (experimental, not production-ready)

#### 4. Audit Logging

**What We Log:**
- All operator actions (mission start/stop, configuration changes)
- All command executions with ACK status
- Authentication events (login, logout, MFA bypass)
- Data access (who queried which drone telemetry)

**Log Retention:** 1 year (configurable for compliance)  
**Log Analysis:** ELK stack (Elasticsearch, Logstash, Kibana)

---

## Deployment Topologies

### Topology 1: Development (Single Machine)

```
Laptop/Desktop (Windows/Mac/Linux)
├─ Docker Compose
│  ├─ Mosquitto (MQTT)
│  ├─ InfluxDB
│  ├─ PostgreSQL
│  ├─ Redis
│  └─ Grafana
├─ Python venv
│  ├─ Mission Control (Flask)
│  └─ SwarmSim (Drone Simulator)
└─ npm run dev
   └─ React UI (Vite dev server)
```

**Use Case:** Local development, unit testing  
**Drone Capacity:** 20 simulated drones  
**Cost:** $0 (open-source tools)

### Topology 2: Field Deployment (On-Premise)

```
Field Server (Rugged NUC, Intel NUC, or Jetson AGX)
├─ Kubernetes (K3s - lightweight)
│  ├─ Mission Control (2 pods)
│  ├─ Fleet Manager (1 pod)
│  ├─ Telemetry Processor (1 pod)
│  ├─ AI Recommender (1 pod, GPU)
│  ├─ EMQX (1 pod)
│  ├─ PostgreSQL (1 pod, persistent volume)
│  └─ InfluxDB (1 pod, persistent volume)
└─ LTE Modem (drone connectivity)
```

**Use Case:** Search & rescue, military ops, remote inspection  
**Drone Capacity:** 50-100 drones  
**Hardware:** $5K-$15K (server + network gear)

### Topology 3: Cloud SaaS (Multi-Tenant)

```
AWS / Azure / GCP
├─ Region 1 (us-east-1)
│  ├─ EKS / AKS / GKE (Kubernetes)
│  │  ├─ Mission Control (5 pods)
│  │  ├─ Fleet Manager (3 pods)
│  │  ├─ Telemetry Processor (10 pods)
│  │  ├─ AI Recommender (5 pods, GPU instances)
│  │  └─ Command Executor (3 pods)
│  ├─ Managed MQTT (EMQX Cloud, HiveMQ Cloud)
│  ├─ Managed PostgreSQL (RDS, Cloud SQL)
│  ├─ Managed InfluxDB (InfluxDB Cloud)
│  └─ CDN (CloudFront, Akamai) for UI assets
├─ Region 2 (us-west-2) - Hot Standby
└─ Global Load Balancer (Route 53, Traffic Manager)
```

**Use Case:** Enterprise SaaS, multi-customer deployment  
**Drone Capacity:** 1000+ drones per customer  
**Cost:** $10K-$50K/month (autoscaling, multi-region)

---

## Technology Stack

### Backend Services

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Mission Control** | Python 3.11, Flask, SocketIO | Rapid development, rich ecosystem |
| **Fleet Manager** | Go 1.21 | High concurrency, low latency |
| **Telemetry Processor** | Apache Kafka Streams | Industry-standard stream processing |
| **AI Recommender** | Python, TensorFlow/PyTorch | ML framework maturity |
| **Command Executor** | Python, pymavlink | MAVLink library availability |

### Data Layer

| Component | Technology | Use Case |
|-----------|-----------|----------|
| **Time-Series DB** | InfluxDB 2.x | Telemetry storage, optimized for time-series |
| **Relational DB** | PostgreSQL 15 | Mission plans, user accounts, audit logs |
| **Cache** | Redis 7.x | Session state, real-time leaderboards |
| **Object Storage** | MinIO (on-prem), S3 (cloud) | Flight logs, video recordings |

### Message Backbone

| Component | Technology | Scale |
|-----------|-----------|-------|
| **MQTT Broker** | Eclipse Mosquitto | Development (<50 drones) |
| **MQTT Broker** | EMQX Enterprise | Production (50-10,000 drones) |
| **Stream Platform** | Apache Kafka | High-throughput analytics pipeline |

### Frontend

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Web Framework** | React 18 | Component reusability, ecosystem |
| **Build Tool** | Vite 5 | Fast HMR, optimized production builds |
| **State Management** | Zustand | Lightweight, less boilerplate than Redux |
| **Map Library** | Leaflet, Mapbox GL JS | Drone position visualization |
| **Charts** | Recharts | Telemetry time-series graphs |

### DevOps & Monitoring

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Container Orchestration** | Kubernetes (EKS, AKS, K3s) | Service deployment, scaling |
| **CI/CD** | GitHub Actions, ArgoCD | Automated testing, GitOps deployment |
| **Metrics** | Prometheus + Grafana | System health, SLA monitoring |
| **Logging** | Loki, ELK Stack | Centralized log aggregation |
| **Tracing** | Jaeger, OpenTelemetry | Distributed request tracing |
| **APM** | New Relic, Datadog (optional) | End-to-end performance monitoring |

---

## Integration Interfaces

### 1. MAVLink Integration (ArduPilot/PX4)

**Protocol:** MAVLink 2.0 over UDP/TCP/Serial  
**Key Messages:**
- `HEARTBEAT` (1 Hz) - Liveness, mode, armed status
- `GLOBAL_POSITION_INT` (10 Hz) - Lat/lon/alt, velocity
- `MISSION_ITEM_INT` - Waypoint upload
- `COMMAND_LONG` - Immediate commands (ARM, RTL, LAND)
- `PARAM_VALUE` - Configuration parameters

**Bridge Implementation:**
```python
from pymavlink import mavutil

# Connect to ArduPilot
mav = mavutil.mavlink_connection('udp:127.0.0.1:14550')

# Wait for heartbeat
mav.wait_heartbeat()

# Send command: ARM
mav.mav.command_long_send(
    mav.target_system,
    mav.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0, 1, 0, 0, 0, 0, 0, 0
)

# Forward to MQTT
mqtt_client.publish(f"fleet/{drone_id}/command_ack", {...})
```

### 2. REST API (Operator Integration)

**Base URL:** `https://aip.example.com/api/v1`  
**Authentication:** Bearer token (JWT)

**Key Endpoints:**
```
GET    /fleet/drones               # List all drones
GET    /fleet/drones/{id}          # Drone details
POST   /missions                   # Create mission
GET    /missions/{id}/status       # Mission progress
POST   /commands/{drone_id}/hold   # Emergency HOLD
GET    /telemetry/{drone_id}/latest # Latest telemetry snapshot
WS     /events                     # Real-time event stream
```

**Example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
     -X POST https://aip.example.com/api/v1/missions \
     -d '{
       "name": "Pipeline Inspection",
       "drones": ["HW-001", "HW-002"],
       "mission_type": "PATROL",
       "waypoints": [...]
     }'
```

### 3. MQTT API (Service-to-Service)

**Broker:** `mqtt.aip.example.com:8883` (TLS)  
**Authentication:** Client certificates

**Topic Schema:**
```
fleet/{drone_id}/telemetry         # Drone publishes
fleet/{drone_id}/command           # Control plane publishes
fleet/{drone_id}/events            # Drone publishes (faults, warnings)
fleet/system/command_ack           # Executor publishes ACKs
fleet/groups/{group_id}/members    # Retained roster
missions/{mission_id}/status       # Mission FSM state
```

**QoS Policy:**
- Telemetry: QoS 0 (fire-and-forget, high frequency)
- Commands: QoS 1 (at-least-once delivery)
- Mission Status: QoS 2 (exactly-once, critical state)

### 4. Webhook Integration (External Systems)

**Use Case:** Notify external systems of mission events

**Configuration:**
```json
{
  "webhook_url": "https://customer.com/api/drone-events",
  "events": ["mission.completed", "drone.fault", "drone.low_battery"],
  "auth": "Bearer secret-token"
}
```

**Payload Example:**
```json
{
  "event_type": "mission.completed",
  "timestamp": "2026-02-09T15:30:00Z",
  "mission_id": "m-12345",
  "drones": ["HW-001", "HW-002"],
  "outcome": "SUCCESS",
  "telemetry_summary": {
    "distance_km": 15.3,
    "flight_time_min": 42,
    "battery_consumed_pct": 68
  }
}
```

---

## Appendix: Reference Architecture Diagrams

### C4 Model: System Context

```
                    ┌─────────────┐
                    │  Operators  │
                    │  (Humans)   │
                    └──────┬──────┘
                           │
                    (Web/Mobile UI)
                           │
                           ↓
    ┌──────────────────────────────────────────┐
    │                                          │
    │    AIP Platform (Command & Control)      │
    │                                          │
    │  - Mission Planning                      │
    │  - Real-time Telemetry                   │
    │  - AI Recommendations                    │
    │  - Fleet Management                      │
    │                                          │
    └────┬─────────────────────────────────┬───┘
         │                                 │
    (MAVLink/MQTT)                   (REST/MQTT)
         │                                 │
         ↓                                 ↓
┌──────────────────┐            ┌──────────────────┐
│  Drone Fleet     │            │  External Systems│
│  (ArduPilot)     │            │  - GIS           │
│                  │            │  - ERP           │
│  - 20-1000 UAVs  │            │  - Video Storage │
└──────────────────┘            └──────────────────┘
```

---

**Document Control**

- **Author:** AIP Architecture Team
- **Reviewers:** CTO, Lead Architect, Security Lead
- **Next Review:** Q3 2026
- **Distribution:** Internal + Customer NDA
