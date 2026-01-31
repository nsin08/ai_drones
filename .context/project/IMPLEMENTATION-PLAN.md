# Implementation Plan: Drone Fleet Ops MVP

**Generated:** 2026-01-31  
**Project:** ai_drones  
**Estimated Duration:** 2 sprints (4 weeks)  
**Total Story Points:** 31 SP  

---

## Sprint Planning

### Sprint 1: Infrastructure + Simulation (13 SP, 2 weeks)

**Goal:** Operational MQTT infrastructure, complete simulation pipeline (fleet + faults)

**Deliverables:**
- Docker-based MQTT broker running
- Fleet simulator publishing telemetry (20+ drones)
- Fault injector transforming raw → realistic telemetry
- Schema validation in place
- Basic monitoring/debugging capability

### Sprint 2: Planning + AI + Integration (18 SP, 2 weeks)

**Goal:** Complete group planner, AI recommender, end-to-end demo

**Deliverables:**
- Group planner emitting per-drone plans for 3 mission types
- AI rules engine publishing recommendations
- Asset simulator for ESCORT missions
- Integration test suite (5 fault scenarios)
- Demo runbook with evidence

---

## Work Breakdown Structure

### Epic 1: MQTT Infrastructure & Schemas

**Epic Goal:** Establish reliable MQTT messaging backbone with validated schemas

#### Story 1.1: Docker Compose + Mosquitto Setup
- **Priority:** P0 (blocker for all sim work)
- **Story Points:** 1
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] `ops/docker-compose.yml` defines Mosquitto service (port 1883, no auth)
- [ ] `ops/mosquitto/mosquitto.conf` configured with:
  - `listener 1883`
  - `allow_anonymous true`
  - Persistence enabled
- [ ] `docker compose up -d` starts broker successfully
- [ ] Verify with `mosquitto_sub -h localhost -t '#' -v`

**Implementation Notes:**
- Use official `eclipse-mosquitto:2` image
- Mount config volume for mosquitto.conf
- Expose port 1883 to host (for Python clients)

**Tests:**
- Manual: Publish test message, verify subscriber receives it
- Automated: Not required for MVP

**Estimated Time:** 2 hours

---

#### Story 1.2: Message Schema Validation Library
- **Priority:** P0 (foundation for all components)
- **Story Points:** 2
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] Create `sim/schemas.py` module that loads all 5 JSON schemas
- [ ] Provide `validate_telemetry(msg)`, `validate_intent(msg)`, etc. functions
- [ ] All simulator components use schema validation before publishing
- [ ] Invalid messages raise `jsonschema.ValidationError` with clear message

**Implementation Notes:**
```python
# sim/schemas.py
import json
import jsonschema
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent.parent / "docs" / "05_message_schemas"

def load_schema(name: str):
    with open(SCHEMA_DIR / f"{name}.schema.json") as f:
        return json.load(f)

TELEMETRY_SCHEMA = load_schema("telemetry")
INTENT_SCHEMA = load_schema("intent")
# ... etc

def validate_telemetry(msg: dict):
    jsonschema.validate(msg, TELEMETRY_SCHEMA)
```

**Tests:**
- Unit tests with valid/invalid messages for each schema
- Test file: `tests/test_schemas.py`

**Estimated Time:** 4 hours

---

### Epic 2: Fleet Simulation Pipeline

**Epic Goal:** Generate realistic telemetry stream from 20+ simulated drones

#### Story 2.1: Fleet Simulator Enhancement
- **Priority:** P0
- **Story Points:** 2
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] `sim/fleet_simulator.py` exists and runs (already present)
- [ ] Validate output against `telemetry.schema.json`
- [ ] Publishes to `raw/fleet/<droneId>/telemetry` at 1 Hz
- [ ] Supports `--drones N` (default 12, test with 20+)
- [ ] Publishes health messages to `raw/fleet/<droneId>/health` every 5s

**Implementation Notes:**
- Code mostly exists; add schema validation
- Add `--config` option to load initial fleet positions from JSON

**Tests:**
- Integration test: Start simulator, verify 20 drones publish for 30s
- Verify message rate (should be ~1 Hz per drone)

**Estimated Time:** 4 hours

---

#### Story 2.2: Fault Injector Implementation
- **Priority:** P0 (critical for acceptance criteria)
- **Story Points:** 5
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] `sim/fault_injector.py` subscribes to `raw/fleet/<droneId>/telemetry`
- [ ] Implements 5 fault models:
  1. **RF_LOSS_BURST**: Drop telemetry for 8s every 120s
  2. **GNSS_MULTIPATH**: Position jumps (±20m) + HDOP spike to 6.0
  3. **EKF_UNHEALTHY**: Set `ekf_ok=false` for 20s
  4. **THRUST_SHORTFALL**: Reduce climb rate, increase current draw
  5. **BATTERY_SAG**: Nonlinear drop below 25%
- [ ] Publishes modified telemetry to `fleet/<droneId>/telemetry`
- [ ] Publishes fault events to `fleet/<droneId>/events` when faults activate/clear
- [ ] Configuration via `--faults` flag (e.g., `--faults RF_LOSS_BURST,GNSS_MULTIPATH`)

**Implementation Notes:**
```python
# Fault model structure
class FaultModel:
    def apply(self, telemetry: dict) -> tuple[dict, list[str]]:
        # Returns: (modified_telemetry, active_faults)
        pass

class RFLossBurst(FaultModel):
    def __init__(self):
        self.last_burst = 0
        self.in_burst = False
    
    def apply(self, telem):
        now = time.time()
        if now - self.last_burst > 120:  # Every 120s
            self.in_burst = True
            self.last_burst = now
        
        if self.in_burst and now - self.last_burst > 8:  # 8s burst
            self.in_burst = False
        
        if self.in_burst:
            return None, ["RF_LOSS_BURST"]  # Drop message
        return telem, []
```

**Tests:**
- Unit tests for each fault model in isolation
- Integration test: Run simulator + injector, verify fault events published
- Test matrix (per `09_test_plan_fault_injection.md`)

**Estimated Time:** 10 hours

---

### Epic 3: Group Mission Planning

**Epic Goal:** Convert group intents into per-drone role-based plans

#### Story 3.1: Group Planner Core Logic
- **Priority:** P0
- **Story Points:** 8
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] `sim/group_planner.py` subscribes to `fleet/groups/<groupId>/intent`
- [ ] Parses intent (mission type, formation, constraints)
- [ ] Loads group membership from `fleet/groups/<groupId>/members.json`
- [ ] Loads drone roles from `fleet/<droneId>/role.json`
- [ ] Emits plans:
  - `fleet/groups/<groupId>/plan/<intentId>` (group-level plan)
  - `fleet/<droneId>/plan/<intentId>` (per-drone tasks)
- [ ] Supports 3 mission types:
  1. **PATROL**: Route/polygon with role-based offsets
  2. **ESCORT**: Formation around moving asset
  3. **PERIMETER_GUARD**: Sector assignments with rotations

**Implementation Notes:**
```python
# Formation geometry for PATROL (LINE)
def compute_line_formation(leader_pos, spacing_m, num_drones):
    positions = []
    for i in range(num_drones):
        offset_m = (i - num_drones // 2) * spacing_m
        # Apply offset perpendicular to leader heading
        positions.append(apply_offset(leader_pos, offset_m))
    return positions

# Role assignment priority
ROLE_PRIORITY = {
    "LEADER": 1,
    "POINT_MAN": 2,
    "WINGMAN": 3,
    "SCOUT": 4,
    "RELAY": 5
}
```

**Complexity Drivers:**
- Formation geometry calculations (LINE/WEDGE/BOX)
- Role-based task assignment (LEADER coordinates, POINT_MAN advances 50m)
- Dynamic replanning on faults (future: MVP uses static plans)

**Tests:**
- Unit tests for formation geometry functions
- Integration tests for each mission type with 5-drone group
- Verify plan schema validation

**Estimated Time:** 16 hours

---

### Epic 4: AI Advisory System

**Epic Goal:** Rules-based AI publishing recommendations based on telemetry patterns

#### Story 4.1: Rules Engine Implementation
- **Priority:** P0
- **Story Points:** 5
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] `sim/simple_rules_ai.py` subscribes to:
  - `fleet/<droneId>/telemetry`
  - `fleet/<droneId>/events`
- [ ] Implements threshold-based rules:
  1. **Telemetry stale** (>5s gap) → Recommend HOLD/RTL
  2. **Low battery** (<25% + role priority) → Recommend role swap or RTL
  3. **GPS anomaly** (HDOP > 5.0) → Recommend HOLD/replan
  4. **EKF unhealthy** → Recommend LAND (CRITICAL severity)
  5. **RF loss burst** → Recommend reduce speed or HOLD
- [ ] Publishes recommendations to:
  - `fleet/<droneId>/ai/recommendation` (drone-specific)
  - `fleet/groups/<groupId>/ai/recommendation` (group-wide)
- [ ] Each recommendation includes:
  - Evidence (telemetry snapshot + threshold violated)
  - Proposed action (HOLD/RTL/LAND/SWAP_ROLE/etc.)
  - Severity (INFO/WARN/CRITICAL)

**Implementation Notes:**
```python
class TelemetryStaleRule:
    def __init__(self, threshold_s=5.0):
        self.last_seen = {}
        self.threshold = threshold_s
    
    def evaluate(self, drone_id, telemetry):
        now = time.time()
        gap = now - self.last_seen.get(drone_id, now)
        self.last_seen[drone_id] = now
        
        if gap > self.threshold:
            return {
                "recommendationId": f"REC-{uuid4()}",
                "ts": now_rfc3339(),
                "scope": "DRONE",
                "severity": "WARN",
                "summary": f"Telemetry gap {gap:.1f}s exceeds threshold",
                "evidence": {"gap_s": gap, "threshold_s": self.threshold},
                "proposed_action": {
                    "type": "HOLD",
                    "targetDroneId": drone_id,
                    "requires_human_approve": True
                }
            }
        return None
```

**Tests:**
- Unit tests for each rule with mocked telemetry
- Integration test: Run simulator + injector + AI, verify recommendations appear

**Estimated Time:** 10 hours

---

### Epic 5: Asset Simulation & ESCORT Support

**Epic Goal:** Moving asset feed for ESCORT mission demonstrations

#### Story 5.1: Asset Simulator Completion
- **Priority:** P1 (required for ESCORT demo)
- **Story Points:** 3
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] `sim/asset_simulator.py` publishes to `assets/<assetId>/pos` at 0.5 Hz
- [ ] Supports configurable path (waypoints or simple linear motion)
- [ ] Position format matches expected by group planner
- [ ] Can simulate moving truck (ASSET-TRUCK-07) for ESCORT demo

**Implementation Notes:**
- Load asset path from `assets/<assetId>/path.json`
- Simple linear interpolation between waypoints
- Publish lat/lon/alt/heading/speed

**Tests:**
- Integration test: Run asset simulator, verify group planner consumes position feed

**Estimated Time:** 6 hours

---

### Epic 6: Integration & Validation

**Epic Goal:** End-to-end testing and demo readiness

#### Story 6.1: Fault Injection Test Matrix
- **Priority:** P0 (acceptance criterion)
- **Story Points:** 5
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] Implement test suite per `09_test_plan_fault_injection.md`
- [ ] Test 5 fault scenarios with 5-drone group:
  1. RF_LOSS_BURST → Verify telemetry stale alert + AI recommendation
  2. GNSS_MULTIPATH → Verify GPS anomaly event + AI recommendation
  3. EKF_UNHEALTHY → Verify critical alert + LAND recommendation
  4. THRUST_SHORTFALL → Verify performance degradation + reduce speed recommendation
  5. BATTERY_SAG → Verify early warning + role swap suggestion
- [ ] Each test asserts:
  - Fault event published to `fleet/<droneId>/events`
  - AI recommendation published within 2s
  - Recommendation includes correct evidence and proposed action

**Implementation Notes:**
```python
# tests/integration/test_fault_injection.py
def test_rf_loss_burst():
    # Start fleet simulator (5 drones)
    # Start fault injector with RF_LOSS_BURST enabled on D001
    # Subscribe to fleet/D001/events and fleet/D001/ai/recommendation
    # Wait for fault activation (120s)
    # Assert: Event received with fault="RF_LOSS_BURST"
    # Assert: AI recommendation received with type="HOLD" or "RTL"
    pass
```

**Tests:**
- 5 integration tests (one per fault scenario)
- Use pytest with MQTT test fixtures

**Estimated Time:** 10 hours

---

#### Story 6.2: End-to-End Demo Runbook
- **Priority:** P0 (deliverable for stakeholders)
- **Story Points:** 2
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] Create `docs/15_e2e_demo_runbook.md` with step-by-step instructions
- [ ] Covers all 3 mission types (PATROL, ESCORT, PERIMETER_GUARD)
- [ ] Includes screenshots/terminal output examples
- [ ] Documents expected MQTT messages at each step
- [ ] Validates against acceptance criteria in `08_acceptance_criteria.md`

**Implementation Notes:**
- Use mqtt.cool web UI for visual demonstration
- Document terminal commands for each simulator component
- Provide example intent JSON for copy-paste

**Estimated Time:** 4 hours

---

#### Story 6.3: Configuration Examples & Fleet Setup
- **Priority:** P1 (nice-to-have for MVP)
- **Story Points:** 2
- **Assignee:** @nsin08

**Acceptance Criteria:**
- [ ] Validate existing fleet configs in `fleet/D001-D005/`
- [ ] Create example group config: `fleet/groups/G01/members.json` and `intent.json`
- [ ] Create `config.example.json` for simulator initialization
- [ ] Document config file format in README

**Implementation Notes:**
- Fleet configs already exist; verify they match current schemas
- Group G01 should have 5 drones with all 5 roles assigned

**Estimated Time:** 4 hours

---

## Critical Path Analysis

**Longest Dependency Chain:** 13 days (assuming 1 SP = ~2 hours)

```
Story 1.1 (Docker) → Story 1.2 (Schemas) → Story 2.1 (Fleet Sim) → 
Story 2.2 (Fault Injector) → Story 3.1 (Planner) → Story 6.1 (Tests)
```

**Parallelizable Work:**
- Story 4.1 (AI) can start after Story 1.2 (Schemas)
- Story 5.1 (Asset Sim) can start after Story 1.2 (Schemas)
- Story 6.2 (Demo Runbook) can be drafted early, finalized at end

---

## Sprint Breakdown

### Sprint 1 (Week 1-2): Infrastructure + Simulation

**Day 1-2:**
- ✅ Story 1.1: Docker + Mosquitto (1 SP)
- ✅ Story 1.2: Schema validation library (2 SP)

**Day 3-4:**
- ✅ Story 2.1: Fleet simulator enhancement (2 SP)

**Day 5-9:**
- ✅ Story 2.2: Fault injector (5 SP)

**Day 10:**
- ✅ Sprint 1 integration test (simulators + fault injector working end-to-end)

**Sprint 1 Demo:**
- Show 20 drones publishing telemetry
- Show fault injection triggering events (RF loss, GPS anomaly)

---

### Sprint 2 (Week 3-4): Planning + AI + Demo

**Day 1-5:**
- ✅ Story 3.1: Group planner (8 SP)

**Day 6-8:**
- ✅ Story 4.1: AI rules engine (5 SP)
- ⏭️ (Parallel) Story 5.1: Asset simulator (3 SP)

**Day 9-10:**
- ✅ Story 6.1: Fault injection test matrix (5 SP)

**Day 11-12:**
- ✅ Story 6.2: Demo runbook (2 SP)
- ✅ Story 6.3: Config examples (2 SP)

**Day 13-14:**
- ✅ Sprint 2 retrospective
- ✅ Final demo preparation
- ✅ Record demo video (optional)

**Sprint 2 Demo:**
- Show all 3 mission types (PATROL, ESCORT, PERIMETER_GUARD)
- Show AI recommendations in response to faults
- Show operator ACK workflow via MQTT

---

## Definition of Ready (DoR) Checklist

Before starting implementation of any story:
- [ ] Story has clear acceptance criteria
- [ ] Story is sized (story points assigned)
- [ ] Dependencies identified and available
- [ ] Technical approach documented
- [ ] Test strategy defined

---

## Definition of Done (DoD) Checklist

Before marking any story as complete:
- [ ] Code written and committed to feature branch
- [ ] Unit tests written and passing (where applicable)
- [ ] Integration tests written and passing (where applicable)
- [ ] Code reviewed (self-review for solo developer)
- [ ] Documentation updated (README, inline comments)
- [ ] Manual testing completed (per acceptance criteria)
- [ ] PR opened and linked to story (per Rule 08)

---

## Risk Mitigation Plan

| Risk | Mitigation |
|------|------------|
| Group planner complexity exceeds estimate | Break into sub-stories; defer dynamic replanning to v2 |
| Fault injection doesn't feel realistic | Validate with SITL early; accept best-effort for MVP |
| MQTT performance issues at scale | Load test with 50+ drones early in Sprint 1 |
| Integration test flakiness | Use deterministic timing; add retry logic for MQTT |
| Mission Planner integration friction | Accept manual workflow; document thoroughly |

---

## Success Metrics

**MVP Complete When:**
- ✅ All acceptance criteria in `08_acceptance_criteria.md` satisfied
- ✅ 5 fault injection tests passing
- ✅ Demo runbook validated with successful demo
- ✅ All code committed and pushed to GitHub
- ✅ README updated with setup instructions

**Quality Gates:**
- Unit test coverage ≥80% (for core logic: planner, AI, fault injector)
- Integration tests for all 3 mission types passing
- No critical bugs open
- All schema validation in place (no invalid messages published)

---

## Next Steps (Immediate Actions)

1. **Create GitHub Issues** (per space_framework Rule 04):
   - Convert each story above into a GitHub Issue
   - Label: `type:story`, `state:approved`
   - Link to this implementation plan

2. **Setup Sprint 1 Project Board**:
   - Create columns: Backlog, Ready, In Progress, In Review, Done
   - Move Sprint 1 stories to Ready

3. **Initialize Branch Protection** (per setup docs):
   - Run `setup-labels.sh` script
   - Configure branch protection for `main`

4. **Begin Story 1.1** (Docker Compose):
   - Create feature branch: `feature/1-docker-mosquitto-setup`
   - Implement acceptance criteria
   - Open PR with evidence mapping

---

## Appendix: Technology Stack Summary

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| **Broker** | Eclipse Mosquitto | 2.x | MQTT 3.1.1/5.0 |
| **Language** | Python | 3.11+ | Type hints, async support |
| **MQTT Client** | paho-mqtt | 2.1.0 | Stable, well-documented |
| **Validation** | jsonschema | 4.23.0 | JSON Schema Draft 07 |
| **Container** | Docker Desktop | Latest | Windows compatibility |
| **Testing** | pytest | Latest | Unit + integration tests |
| **GCS (Optional)** | Mission Planner | Latest | Manual execution demos |

---

**Document Status:** ✅ Ready for Implementation  
**Next Review:** End of Sprint 1 (2 weeks)  
**Owner:** @nsin08
