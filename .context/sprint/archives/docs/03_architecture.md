# System Architecture & Design

**Last Updated:** February 1, 2026  
**Audience:** Technical team, architects  
**Status:** MVP / PoC Phase

---

## High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 5: PRESENTATION & HUMAN INTERFACE                        │
│  ┌────────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │ Mission Control UI │  │ Grafana Dash   │  │ Mission Planner│
│  │ (Web, port 5000)   │  │ (Telemetry)    │  │ SITL (Windows) │
│  └────────────────────┘  └────────────────┘  └───────────────┘ │
│         Flask App         (Optional TS View)   (Optional Manual)  │
└──────────────────────┬──────────────────────────────────────────┘
                       │ (WebSocket + REST)
┌──────────────────────▼──────────────────────────────────────────┐
│  Layer 4: APPLICATION & ORCHESTRATION                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Mission Control Backend (`mission_control.py`)          │   │
│  │  • Mission lifecycle mgmt (create → plan → arm → exec) │   │
│  │  • Command validation & routing to drones              │   │
│  │  • WebSocket event broadcasting                        │   │
│  │  • Subprocess management (simulators)                  │   │
│  │                                                         │   │
│  │ Fleet Services                                          │   │
│  │  • Group Planner (`group_planner.py`)                  │   │
│  │    - Converts intent → per-drone plans                 │   │
│  │  • Rules AI (`simple_rules_ai.py`)                     │   │
│  │    - Telemetry analysis → recommendations              │   │
│  │  • Fault Injector (`fault_injector.py`)                │   │
│  │    - Overlays realistic fault symptoms                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ (MQTT publish/subscribe)
┌──────────────────────▼──────────────────────────────────────────┐
│  Layer 3: MESSAGING BUS (MQTT)                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ MQTT Broker (Eclipse Mosquitto, port 1883)              │   │
│  │  Topic Structure:                                       │   │
│  │   • fleet/{id}/telemetry   (drone → broker)            │   │
│  │   • fleet/{id}/command     (backend → drone)           │   │
│  │   • fleet/{id}/status      (drone heartbeat)           │   │
│  │   • fleet/{id}/events      (drone → broker)            │   │
│  │   • fleet/groups/*/intent  (backend → drones)          │   │
│  │   • fleet/groups/*/plan    (backend → drones)          │   │
│  │   • fleet/groups/*/status  (group health)              │   │
│  │   • fleet/*/ai/recommendation (AI → dashboard)         │   │
│  │   • fleet/acks/*           (operator → backend)        │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ (Telegraf scrape + InfluxDB write)
┌──────────────────────▼──────────────────────────────────────────┐
│  Layer 2: DATA PERSISTENCE & ANALYTICS                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ InfluxDB         │  │ PostgreSQL       │  │ File Storage │  │
│  │ (port 8086)      │  │ (port 5432)      │  │ (logs/)      │  │
│  │ • Telemetry TS   │  │ • Mission logs   │  │ • Flight rec │  │
│  │ • Events TS      │  │ • Audit trail    │  │ • Fault data │  │
│  │ • AI metrics     │  │ • User mgmt      │  │ • Playback   │  │
│  │ 2Hz × 12 drones  │  │ • Decisions      │  │              │  │
│  │ = 24 writes/sec  │  │                  │  │              │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│  Layer 1: EDGE DEVICES & SIMULATION                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Fleet Simulator (`fleet_simulator.py`)                   │   │
│  │  • Mock N drones (position, speed, battery, attitude)   │   │
│  │  • Realistic kinematics (accel, drag model)             │   │
│  │  • Publishes: raw/fleet/{id}/telemetry (simulator)     │   │
│  │                                                          │   │
│  │ Fault Injector (overlaid on simulator)                   │   │
│  │  • RF loss bursts (telemetry gaps)                      │   │
│  │  • GNSS multipath symptoms (pos noise + bias)           │   │
│  │  • EKF unhealthy (variance spike)                       │   │
│  │  • Thrust shortfall (climb rate degrade)                │   │
│  │  • Battery sag (voltage sag + dynamic load impact)      │   │
│  │  • Publishes: fleet/{id}/telemetry (normalized)        │   │
│  │              fleet/{id}/events (fault triggers)         │   │
│  │                                                          │   │
│  │ Asset Simulator (for ESCORT missions)                    │   │
│  │  • Mock moving target (VIP transport, asset)            │   │
│  │  • Publishes: fleet/assets/{id}/position                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  (Real Drone Flight Stack — Future)                             │
│  ┌────────────────────┐  ┌──────────────────┐                  │
│  │ Flight Controller  │  │ Companion CPU    │                  │
│  │ (Pixhawk/Cube)     │  │ (Raspberry Pi)   │                  │
│  │ • Stabilization    │  │ • MQTT client    │                  │
│  │ • Navigation       │  │ • MAVLink bridge │                  │
│  │ • Safety (RTL)     │  │ • Payload ctrl   │                  │
│  └────────────────────┘  └──────────────────┘                  │
│  Sensors: GPS, IMU, Barometer, Compass, Rangefinder, Camera    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architectural Principles

### 1. Hexagonal (Ports & Adapters)
- **Domain core** (`poc/src/domain/`) — fault models, telemetry schemas, pure business logic
- **Ports** (`poc/src/ports/`) — interfaces for message broker, persistence, external systems
- **Adapters** (`poc/src/adapters/`) — MQTT broker (Mosquitto), memory broker (testing)

**Benefit:** Decoupled from MQTT/database; easy to test in isolation; reusable across UI/backend.

### 2. Event-Driven
- Drones (simulated) publish telemetry events to MQTT
- Planners subscribe, process, and publish plans
- AI monitors events and publishes recommendations
- Operators subscribe to all events and can ACK recommendations

**Benefit:** Loosely coupled services; real-time; natural fit for distributed drones.

### 3. Domain-Driven
- **Telemetry domain:** position, velocity, attitude, battery, sensor health
- **Fault domain:** RF loss, GNSS multipath, EKF, thrust, battery sag
- **Mission domain:** intents, plans, roles, groups, state machine
- **Recommendation domain:** evidence, proposed action, audit trail

**Benefit:** Clear vocabulary; testable; domain experts can review logic.

### 4. TDD-First (Tests Define Behavior)
- All fault models have unit tests (test coverage > 90%)
- Integration tests verify end-to-end MQTT flows
- No "happy path only" — tests exercise edge cases and error scenarios

**Benefit:** Confidence in non-hardware demo; reproducible faults; easy to refactor.

---

## Core Components

### A. Fleet Simulator (`poc/src/fleet_simulator.py`)

**Responsibility:** Generate realistic telemetry for N mock drones.

**Key Functions:**
```python
class FleetSimulator:
    def __init__(self, num_drones: int, broker: MessageBroker):
        self.drones = [MockDrone(...) for _ in range(num_drones)]
    
    def tick(self, dt: float) -> None:
        """Advance simulation by dt seconds."""
        for drone in self.drones:
            drone.update_position(dt)
            drone.update_battery(dt)
            telemetry = drone.get_telemetry()
            self.broker.publish(f"raw/fleet/{drone.id}/telemetry", telemetry)
```

**Publishes:**
- `raw/fleet/{id}/telemetry` — raw simulator output (before fault injection)
- `raw/fleet/{id}/command_ack` — ack when drone receives command

**Subscribes:**
- `fleet/{id}/command` — receive goto, land, arm, disarm commands

**Output Format:** JSON telemetry (lat, lon, alt, vx, vy, vz, battery %, mode, armed, gps_status)

---

### B. Fault Injector (`poc/src/domain/fault_*.py` + `poc/src/fault_injector.py`)

**Responsibility:** Overlay realistic fault symptoms on simulator telemetry.

**Fault Models (each is a class with TDD-verified logic):**

| Fault | Symptom | Trigger | Recovery |
|-------|---------|---------|----------|
| **RF Loss Burst** | Telemetry gap (no updates for 2–10 sec) | Random (0.1 Hz) | Comms restored, telemetry resumes |
| **GNSS Multipath** | GPS noise (±50 m) + bias (slow drift) | When altitude < 30 m | Recovers over 30 sec |
| **EKF Unhealthy** | Attitude variance spike (> threshold) | Post-multipath or vibration | Recovers over 10 sec |
| **Thrust Shortfall** | Climb rate -20%, accel degraded | Battery < 30% or fault trigger | Recovers on battery restore |
| **Battery Sag** | Voltage sag under load, dynamic load impact | Discharge time | Recovers during hover/low-load |

**Key Design:**
```python
class RFLossBurst:
    """Simulates comms blackout (telemetry gap) for 2–10 sec."""
    def apply(self, telemetry: Telemetry) -> Optional[Telemetry]:
        if self.is_active() and not self.should_publish():
            return None  # Suppress telemetry
        return telemetry

class GNSSMultipath:
    """Simulates GPS noise + bias (multipath indoors/urban)."""
    def apply(self, telemetry: Telemetry) -> Telemetry:
        noise = np.random.normal(0, self.std_dev)
        telemetry.gps_lat += noise
        telemetry.gps_lon += noise
        return telemetry
```

**Publishes:**
- `fleet/{id}/telemetry` — fault-injected telemetry
- `fleet/{id}/events` — fault event markers (RF loss started, GNSS multipath triggered, etc.)

---

### C. Group Planner (`poc/src/group_planner.py`)

**Responsibility:** Convert operator intent (mission type + group definition) → per-drone plans.

**Key Functions:**
```python
class GroupPlanner:
    def plan_patrol(self, intent: PatrolIntent, group: Group) -> Dict[str, Plan]:
        """Generate per-drone plan for PATROL mission."""
        plans = {}
        for i, drone_id in enumerate(group.drone_ids):
            role = group.roles[drone_id]
            offset = self._compute_offset(i, role)
            plan = Plan(
                drone_id=drone_id,
                waypoints=[wp + offset for wp in intent.route],
                speed=intent.speed_mps,
                loiter_time=intent.loiter_time_sec
            )
            plans[drone_id] = plan
        return plans
    
    def plan_escort(self, intent: EscortIntent, group: Group) -> Dict[str, Plan]:
        """Generate per-drone plan for ESCORT mission (adaptive to asset position)."""
        # Subscribes to fleet/assets/{asset_id}/position
        # Computes per-drone offset based on role (POINT_MAN, WINGMAN, SCOUT)
        # Returns adaptive plan (updates as asset moves)
        pass
    
    def plan_perimeter_guard(self, intent: PerimeterGuardIntent, group: Group) -> Dict[str, Plan]:
        """Generate per-drone plan for PERIMETER_GUARD mission."""
        # Divides perimeter into sectors
        # Assigns drones to sectors with relief intervals
        pass
```

**Publishes:**
- `fleet/{id}/plan/{mission_id}` — per-drone plan (JSON: [waypoint, waypoint, ...])
- `fleet/groups/{group_id}/plan/{mission_id}` — group plan metadata (roles, relief schedule, etc.)

**Subscribes:**
- `fleet/intents/{intent_id}` — operator mission intent

---

### D. Rules-Based AI Recommender (`poc/src/simple_rules_ai.py`)

**Responsibility:** Monitor telemetry and fault events; publish advisory recommendations.

**Key Rules:**
```python
class SimpleRulesAI:
    def monitor(self):
        """Poll telemetry; generate recommendations."""
        
        # Rule 1: Battery sag detection
        if any(drone.battery_pct < 30 for drone in fleet):
            self.recommend(
                drone_id=...,
                action="increase_rtl_threshold",
                evidence="Battery < 30%",
                confidence=0.95
            )
        
        # Rule 2: GNSS multipath (low alt + high position variance)
        if drone.altitude_agl < 30 and drone.gps_variance > threshold:
            self.recommend(
                drone_id=...,
                action="climb_to_30m",
                evidence="GNSS multipath detected (low alt + variance spike)",
                confidence=0.85
            )
        
        # Rule 3: RF loss recovery (telemetry gap > 10 sec)
        if drone.telemetry_gap_sec > 10:
            self.recommend(
                drone_id=...,
                action="initiate_rtl",
                evidence="Comms loss > 10 sec",
                confidence=0.99
            )
        
        # Rule 4: Formation breach (PATROL/ESCORT)
        if group.formation_breach_count > group.max_allowed:
            self.recommend(
                group_id=...,
                action="reduce_speed_or_abort",
                evidence=f"Formation breach: {group.formation_breach_count} / {group.max_allowed}",
                confidence=0.90
            )
```

**Publishes:**
- `fleet/{id}/ai/recommendation` — per-drone recommendation (JSON: action, evidence, confidence)
- `fleet/groups/{group_id}/ai/recommendation` — group-level recommendation
- `fleet/ai/metrics` — meta (recommendations/hour, avg confidence, operator ACK rate)

**Subscribes:**
- `fleet/+/telemetry` — all drone telemetry
- `fleet/+/events` — fault events
- `fleet/groups/+/status` — group status (formation, perimeter coverage, etc.)

---

### E. Mission Control Backend (`poc/mission_control.py`)

**Responsibility:** Lifecycle management, command routing, operator interface.

**Key Functions:**
```python
class MissionControl:
    def create_mission(self, operator_input) -> Mission:
        """Operator submits mission intent."""
        intent = Intent(type=..., group_id=..., params=...)
        mission = Mission(intent=intent, state=MissionState.CREATED)
        return mission
    
    def arm_mission(self, mission_id) -> None:
        """Transition PLANNED → ARMED."""
        # Verify all drones armed and healthy
        # Publish arm confirmation
        self.publish(f"fleet/groups/{mission.group_id}/arm_confirmation")
    
    def execute_command(self, drone_id, command) -> None:
        """Route operator command to drone."""
        self.broker.publish(f"fleet/{drone_id}/command", command)
    
    def handle_ack(self, recommendation_id, operator_response) -> None:
        """Operator ACKs AI recommendation."""
        self.log_decision(recommendation_id, operator_response)
        self.publish(f"fleet/acks/{recommendation_id}", operator_response)
```

**Subscribes:**
- `fleet/+/telemetry` — all telemetry (display on dashboard)
- `fleet/+/events` — all events (log, alert)
- `fleet/+/ai/recommendation` — all AI recommendations (display to operator)
- `fleet/acks/+` — operator ACKs (process, log)

**Publishes:**
- `fleet/{id}/command` — command to drone
- `fleet/groups/{group_id}/intent` — broadcast mission intent
- `fleet/groups/{group_id}/plan` — broadcast per-drone plans

---

### F. Persistence & Audit (`postgres + influxdb`)

**Postgres Tables:**
```sql
-- Mission lifecycle
CREATE TABLE missions (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP,
    intent JSONB,
    state ENUM (CREATED, PLANNED, ARMED, IN_PROGRESS, SUSPENDED, ABORT, RECOVERED),
    operator_id UUID
);

-- Decisions & ACKs
CREATE TABLE decisions (
    id UUID PRIMARY KEY,
    mission_id UUID,
    timestamp TIMESTAMP,
    type ENUM (relief, rtl_override, battery_increase, ...),
    decision_text TEXT,
    operator_id UUID,
    confidence FLOAT
);

-- Audit trail
CREATE TABLE audit_log (
    timestamp TIMESTAMP,
    user_id UUID,
    action TEXT,
    details JSONB
);
```

**InfluxDB Measurements:**
```
telemetry (tags: drone_id, group_id | fields: lat, lon, alt, vx, vy, vz, battery_pct, gps_status)
events (tags: drone_id, event_type | fields: severity, details)
ai_metrics (tags: rule_id | fields: confidence, operator_ack_rate)
```

---

## Data Flow: Example Mission (PATROL)

```
t=0: Operator submits PATROL intent
     POST /missions { type: PATROL, group_id: G01, route: [...], speed: 10 }
     
t=1: Mission Control creates mission (state: CREATED)
     
t=2: Group Planner subscribes to mission intent, generates per-drone plans
     Publishes: fleet/{id}/plan/{mission_id} for each drone
     
t=3: Operator reviews plans, clicks "ARM"
     Mission Control: fleet/groups/G01/arm_confirmation
     
t=4: Each drone simulated receives arm command
     Simulator: fleet/{id}/status = "armed"
     
t=5–300: Mission in progress
     Drone 1 publishes: fleet/1/telemetry (position, battery, etc.)
     Drone 2 publishes: fleet/2/telemetry
     ... (all drones, ~2 Hz each)
     
     Fault Injector overlays:
     fleet/1/events (RF loss burst triggered at t=150)
     fleet/2/events (GNSS multipath at t=80)
     
     AI Recommender monitors:
     t=80: Detects GNSS multipath on drone 2 → publishes recommendation
     Operator ACKs via: fleet/acks/rec_001 { action: "acknowledged" }
     
     Mission Control displays all updates on dashboard
     
t=300: Last waypoint reached, drones land
     Mission state: COMPLETED
     All events logged to Postgres + InfluxDB
```

---

## Deployment & Operations

### Local Development (Docker Compose)

```bash
cd ops
docker compose up -d
# Starts: Mosquitto, InfluxDB, Grafana, Telegraf
```

### Running the PoC

```bash
# Terminal 1: Fleet Simulator
cd poc
python fleet_simulator.py --broker localhost --drones 12 --hz 2

# Terminal 2: Mission Control Backend
python mission_control.py --port 5000

# Terminal 3: Open dashboard
# http://localhost:5000

# (Optional) Terminal 4: Mission Planner SITL on Windows
# Already installed; connect to localhost:5760
```

### Production Deployment (Future)

- Kubernetes for orchestration
- Real drone integration (MAVLink over serial/network)
- Cloud MQTT broker (AWS IoT Core, Azure IoT Hub, or self-hosted)
- Persistent storage (cloud database, S3 for telemetry archive)
- Monitoring & alerting (Prometheus + AlertManager)
- CI/CD (GitHub Actions → staging → production)

---

## Key Design Decisions (ADRs)

| Decision | Why | Trade-off |
|----------|-----|-----------|
| **MQTT for messaging** | Lightweight, pub/sub natural for distributed drones | Not guaranteed delivery (use QoS 1 for critical cmds) |
| **Hexagonal architecture** | Testable domain; decoupled from framework | Extra indirection (adapters) |
| **Python + TDD** | Fast iteration, domain logic clear, easy testing | Not suitable for flight control itself (use C++ on autopilot) |
| **Fault models, not simulation** | Symptom-level realism; fast; reproducible | Not physics-accurate (ok for ops demo) |
| **Role-based plans** | Scales to many drones; reduces config | Requires pre-defined roles (flexibility vs. simplicity trade) |
| **AI advisory only** | Builds trust; operators retain authority | Slower response to faults (acceptable for MVP) |

---

## Testing Strategy

### Unit Tests (per domain model)
- Fault injection: RF loss burst, GNSS multipath, EKF, battery sag, thrust shortfall
- Telemetry validation
- Plan generation (PATROL, ESCORT, PERIMETER_GUARD)
- State machine transitions

### Integration Tests
- End-to-end MQTT flows (simulator → planner → mission control)
- Operator commands → drone ACK
- AI recommendation → operator ACK → audit log

### Manual Tests
- Dashboard usability (Mission Control UI)
- Grafana time-series displays
- Mission Planner SITL manual execution

---

## Security & Safety Considerations

1. **Command Authentication:** Verify operator identity before accepting commands
2. **Geofence Enforcement:** Hard constraint; drones reject goto outside geofence
3. **Battery RTL:** Autonomous if battery < threshold (cannot override)
4. **Comms Loss:** Auto-RTL if loss > 60 sec (cannot override)
5. **Audit Trail:** All decisions logged with timestamp + operator ID
6. **Secrets Management:** MQTT credentials in `.env` (not committed)

---

## Next Steps

- [ ] Complete all fault model tests (coverage > 90%)
- [ ] Implement group planner for all three mission types
- [ ] Build Mission Control UI (telemetry display, mission controls, AI recommendations)
- [ ] Add Grafana dashboards for real-time monitoring
- [ ] Write integration tests (end-to-end MQTT flows)
- [ ] Demo to stakeholders
- [ ] Plan MVP release (real drone integration, production deployment)
