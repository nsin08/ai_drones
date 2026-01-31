# Implementation Plan: Drone Fleet Ops MVP

**Generated:** 2026-01-31 (REVISED)  
**Project:** ai_drones  
**Estimated Duration:** 1 sprint (1 week)  
**Total Story Points Remaining:** 9 SP (71% complete)  
**Status:** \u2705 **DEPLOYMENT & TESTING PHASE** (core implementation complete)

---

## Executive Summary

**MAJOR UPDATE:** Comprehensive code review reveals **71% of implementation is already complete**.

**What's Already Done (22 SP):**
- \u2705 `fleet_simulator.py` (100 lines) - Raw telemetry generation
- \u2705 `fault_injector.py` (182 lines) - 5 fault models fully implemented
- \u2705 `group_planner.py` (278 lines) - 3 mission types (PATROL/ESCORT/PERIMETER_GUARD)
- \u2705 `simple_rules_ai.py` (80 lines) - Rules-based recommendations
- \u2705 `asset_simulator.py` (100 lines) - Moving asset feed for ESCORT
- \u2705 `config.example.json` - Fault profiles for D001-D004
- \u2705 Fleet configs (D001-D005 roles)
- \u2705 Group configs (G01 members + intent)
- \u2705 `mosquitto.conf` (4 lines) - Broker configuration
- \u2705 Demo runbook (13_demo_runbook.md)

**What's Remaining (9 SP):**
- \ud83d\udd34 `docker-compose.yml` (1 SP) - 15 lines YAML
- \ud83d\udd34 Integration tests (5 SP) - Fault injection test matrix
- \ud83d\udd34 Demo validation (2 SP) - End-to-end verification
- \ud83d\udd34 Broker deployment (1 SP) - Docker setup + smoke test

**Revised Timeline:** 1 sprint (5 days) vs. original 4 weeks

---

## Sprint Planning

### Sprint 1: Deployment + Integration Testing (9 SP, 1 week)

**Goal:** Deploy MQTT infrastructure, validate all simulators end-to-end, complete demo

**Deliverables:**
- Docker-based MQTT broker running
- All 5 simulators validated in integrated environment
- Integration test suite (5 fault scenarios) passing
- Demo runbook validated with evidence

---

## Work Breakdown Structure

### Epic 1: MQTT Infrastructure Deployment

**Epic Goal:** Deploy operational MQTT broker with Docker

#### Story 1.1: Docker Compose Configuration
- **Priority:** P0 (blocker for all integration work)
- **Story Points:** 1
- **Assignee:** @nsin08
- **Status:** \ud83d\udd34 TODO

**Acceptance Criteria:**
- [ ] `ops/docker-compose.yml` defines Mosquitto service (port 1883, no auth)
- [ ] Service config references `mosquitto/mosquitto.conf` (already complete)
- [ ] `docker compose up -d` starts broker successfully
- [ ] Verify with `docker ps` shows mosquitto container running
- [ ] Smoke test: `mosquitto_sub -h localhost -t '#' -v` connects successfully

**Implementation Notes:**
```yaml
# ops/docker-compose.yml
version: '3.8'
services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mqtt-broker
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
    restart: unless-stopped
```

**Tests:**
- Manual: Publish test message, verify subscriber receives it
- Command: `mosquitto_pub -h localhost -t test -m "hello" && mosquitto_sub -h localhost -t test -C 1`

**Estimated Time:** 1 hour

---

#### Story 1.2: ~~Message Schema Validation Library~~ \u2705 COMPLETE
**Status:** Schemas already defined and used in all simulator components

---

### Epic 2: ~~Fleet Simulation Pipeline~~ \u2705 COMPLETE

**All stories in this epic are complete:**
- \u2705 Story 2.1: Fleet Simulator (fleet_simulator.py exists, 100 lines)
- \u2705 Story 2.2: Fault Injector (fault_injector.py exists, 182 lines, 5 fault models)

---

### Epic 3: ~~Group Mission Planning~~ \u2705 COMPLETE

**All stories in this epic are complete:**
- \u2705 Story 3.1: Group Planner (group_planner.py exists, 278 lines, 3 missions)

---

### Epic 4: ~~AI Advisory System~~ \u2705 COMPLETE

**All stories in this epic are complete:**
- \u2705 Story 4.1: Rules Engine (simple_rules_ai.py exists, 80 lines, 3 rule types)

---

### Epic 5: ~~Asset Simulation & ESCORT Support~~ \u2705 COMPLETE

**All stories in this epic are complete:**
- \u2705 Story 5.1: Asset Simulator (asset_simulator.py exists, 100 lines)

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

#### Story 6.2: End-to-End Demo Validation
- **Priority:** P0 (deliverable for stakeholders)
- **Story Points:** 2
- **Assignee:** @nsin08
- **Status:** \ud83d\udd34 TODO

**Acceptance Criteria:**
- [ ] Validate existing demo runbook (`docs/13_demo_runbook.md`)
- [ ] Execute all steps in runbook without errors
- [ ] Verify all 3 mission types work (PATROL, ESCORT, PERIMETER_GUARD)
- [ ] Document actual MQTT messages observed (screenshots/logs)
- [ ] Validate against acceptance criteria in `08_acceptance_criteria.md`

**Implementation Notes:**
- Demo runbook already exists and is comprehensive
- Use mqtt.cool web UI or mosquitto_sub for monitoring
- Execute with G01 group (5 drones: D001-D005)
- Verify fault injection triggers AI recommendations

**Estimated Time:** 4 hours

---

#### Story 6.3: ~~Configuration Examples & Fleet Setup~~ \u2705 COMPLETE
**Status:** All configs already exist:
- \u2705 `config.example.json` (fault profiles)
- \u2705 Fleet roles: D001-D005 (5 role files)
- \u2705 Group G01: members + intent JSON

---

## Critical Path Analysis

**Revised Critical Path:** 3 days (down from 13 days)

```
Story 1.1 (Docker) [1 SP, Day 1] → 
Story 6.1 (Integration Tests) [5 SP, Days 2-3] →
Story 6.2 (Demo Validation) [2 SP, Day 4]
```

**No Parallelizable Work:** All simulators and configs are complete

---

## Sprint Breakdown

### Sprint 1 (Week 1): Deployment + Testing

**Day 1:**
- \u2705 Story 1.1: Docker Compose (1 SP)
- Smoke test: Verify Mosquitto broker running
- Smoke test: Run each simulator individually

**Day 2-3:**
- \u2705 Story 6.1: Fault injection test matrix (5 SP)
- Execute all 5 fault scenarios
- Collect evidence (MQTT logs + AI recommendations)

**Day 4:**
- \u2705 Story 6.2: Demo validation (2 SP)
- Execute demo runbook end-to-end
- Verify all 3 mission types
- Collect demo artifacts

**Day 5:**
- \u2705 Sprint retrospective
- \u2705 Final documentation update
- \u2705 Record demo video (optional)

**Sprint 1 Demo:**
- Show all 3 mission types (PATROL, ESCORT, PERIMETER_GUARD)
- Show fault injection triggering AI recommendations
- Show operator ACK workflow via MQTT (manual)

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
   - Story 1.1: Docker Compose Configuration (1 SP)
   - Story 6.1: Fault Injection Test Matrix (5 SP)
   - Story 6.2: End-to-End Demo Validation (2 SP)
   - Label: `type:story`, `state:ready`
   - Link to this implementation plan

2. **Setup Sprint 1 Project Board**:
   - Create columns: Backlog, Ready, In Progress, In Review, Done
   - Move all 3 stories to Ready

3. **Initialize Branch Protection** (per setup docs):
   - Run `.context/temp/setup-labels.sh` script
   - Configure branch protection for `main`

4. **Begin Story 1.1** (Docker Compose):
   - Create feature branch: `feature/1-docker-compose-setup`
   - Create `ops/docker-compose.yml` (15 lines)
   - Test with `docker compose up -d`
   - Open PR with evidence mapping

---

## Appendix: Code Inventory Summary

### Complete Simulator Components (\u2705 22 SP worth)

| File | Lines | Status | Description |
|------|-------|--------|-------------|
| `fleet_simulator.py` | 100 | \u2705 COMPLETE | Raw telemetry (12-20+ drones @ 1 Hz) |
| `fault_injector.py` | 182 | \u2705 COMPLETE | 5 fault models (RF/GNSS/EKF/thrust/battery) |
| `group_planner.py` | 278 | \u2705 COMPLETE | 3 missions (PATROL/ESCORT/PERIMETER_GUARD) |
| `simple_rules_ai.py` | 80 | \u2705 COMPLETE | Rules engine (3 rule types) |
| `asset_simulator.py` | 100 | \u2705 COMPLETE | Moving asset feed (circular/linear) |
| `config.example.json` | 24 | \u2705 COMPLETE | Fault profiles (D001-D004) |
| `mosquitto.conf` | 4 | \u2705 COMPLETE | Broker config (listener 1883, anonymous) |
| Fleet configs | 5 files | \u2705 COMPLETE | D001-D005 role assignments |
| Group configs | 2 files | \u2705 COMPLETE | G01 members + intent |
| Demo runbook | 1 file | \u2705 COMPLETE | Step-by-step instructions |

**Total Lines of Production Code:** ~740 lines Python (all functional)

### Remaining Work (\ud83d\udd34 9 SP)

| Task | Effort | Type |
|------|--------|------|
| Docker Compose YAML | 1 SP | Config file creation |
| Integration test suite | 5 SP | Test implementation |
| Demo validation | 2 SP | Manual testing + documentation |
| Broker deployment | 1 SP | Docker command execution |

---

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
