# Feasibility & Dependency Report: Drone Fleet Ops MVP

**Generated:** 2026-01-31  
**Project:** ai_drones (https://github.com/nsin08/ai_drones)  
**Scope:** Advisory-only MQTT-based fleet operations with ArduPilot integration  

---

## Executive Summary

**Verdict:** ✅ **FEASIBLE** for MVP scope with existing tech stack

**Confidence:** HIGH (85%)

**Key Strengths:**
- Well-scoped MVP boundaries (no real hardware, advisory-only)
- Mature dependencies (MQTT, Python 3.11, Docker)
- Safe execution model (operator-in-loop via Mission Planner)
- Clear incremental path from simulation → SITL → real drones

**Key Risks:**
- Mission Planner integration requires manual verification (low automation)
- Fault injection realism depends on accurate ArduPilot telemetry modeling
- Group coordination logic complexity (planner state machine)

---

## 1. Requirements Analysis

### 1.1 Core Functional Requirements

| ID | Requirement | Priority | Complexity | Status |
|----|-------------|----------|------------|--------|
| FR-01 | Fleet monitoring (20+ drones, 1 Hz telemetry) | P0 | Low | ✅ Achievable |
| FR-02 | 5 role types (LEADER, POINT_MAN, WINGMAN, SCOUT, RELAY) | P0 | Medium | ✅ Achievable |
| FR-03 | 3 mission types (PATROL, ESCORT, PERIMETER_GUARD) | P0 | Medium | ✅ Achievable |
| FR-04 | Group formation logic (LINE, WEDGE, BOX) | P0 | Medium | ✅ Achievable |
| FR-05 | Fault injection (5 fault types) | P0 | Medium | ✅ Achievable |
| FR-06 | AI recommendations (rules-based v1) | P0 | Low | ✅ Achievable |
| FR-07 | Operator ACK workflow via MQTT | P0 | Low | ✅ Achievable |
| FR-08 | Mission Planner manual execution | P1 | Low | ⚠️ Manual testing |

### 1.2 Non-Functional Requirements

| ID | Requirement | Target | Feasibility |
|----|-------------|--------|-------------|
| NFR-01 | Telemetry latency (end-to-end) | <500ms | ✅ MQTT QoS=1 |
| NFR-02 | Fault injection realism | ArduPilot-like | ⚠️ Best-effort |
| NFR-03 | Scale (concurrent drones) | 20+ | ✅ MQTT handles 1000s |
| NFR-04 | Windows compatibility | Required | ✅ Docker Desktop |
| NFR-05 | No real hardware required | MVP constraint | ✅ Simulator-only |

---

## 2. Dependency Analysis

### 2.1 External Dependencies

#### MQTT Broker (Eclipse Mosquitto)
- **Version:** 2.x (via Docker)
- **Status:** ✅ STABLE
- **Risk:** LOW
- **Notes:** 
  - Proven MQTT 3.1.1/5.0 implementation
  - Handles 1000s of clients with minimal config
  - No auth/ACL required for MVP (localhost-only)

#### Python 3.11
- **Status:** ✅ STABLE
- **Risk:** LOW
- **Required packages:**
  - `paho-mqtt==2.1.0` (MQTT client) ✅ 
  - `jsonschema==4.23.0` (message validation) ✅ 
  - `python-dateutil==2.9.0.post0` (timestamp handling) ✅ 

#### Docker Desktop (Windows)
- **Status:** ✅ AVAILABLE
- **Risk:** LOW
- **Notes:** Required for Mosquitto broker; widely adopted on Windows

#### Mission Planner (Optional for SITL)
- **Status:** ⚠️ MANUAL INTEGRATION
- **Risk:** MEDIUM
- **Notes:**
  - Not required for core MVP functionality
  - Used only for manual execution demos
  - Requires separate SITL setup (ArduPilot)

### 2.2 Internal Dependencies (Project Code)

| Component | Status | Implementation Complexity | Priority |
|-----------|--------|---------------------------|----------|
| `fleet_simulator.py` | ✅ EXISTS | Low (100 lines) | P0 |
| `fault_injector.py` | 🔴 MISSING | Medium (200 lines) | P0 |
| `group_planner.py` | ✅ EXISTS | High (300+ lines) | P0 |
| `asset_simulator.py` | ✅ EXISTS | Low (150 lines) | P1 |
| `simple_rules_ai.py` | ✅ EXISTS | Medium (250 lines) | P0 |
| MQTT topic schemas (5 types) | ✅ DEFINED | N/A | P0 |
| Docker compose config | 🔴 EMPTY | Low (20 lines) | P0 |
| Config examples | ⚠️ PARTIAL | Low (50 lines) | P1 |

**Legend:**
- ✅ EXISTS: Code present and ready
- 🔴 MISSING: Code not yet created
- ⚠️ PARTIAL: Incomplete or needs expansion

---

## 3. Technical Feasibility Assessment

### 3.1 Architecture Validation

**MQTT-Based Orchestration:** ✅ FEASIBLE
- Decoupled pub/sub model proven for IoT/robotics
- Topic taxonomy well-designed:
  - `raw/fleet/<droneId>/telemetry` → `fleet/<droneId>/telemetry` (fault injection flow)
  - `fleet/groups/<groupId>/intent` → `fleet/groups/<groupId>/plan/<intentId>` (planner flow)
  - `fleet/<droneId>/ai/recommendation` (AI advisory output)
- QoS=1 provides sufficient reliability for MVP

**Simulator Approach:** ✅ FEASIBLE
- `fleet_simulator.py` generates synthetic telemetry at 1 Hz
- Simple random walk movement model (sufficient for MVP)
- No 3D physics required (acceptable per scope)

**Fault Injection Strategy:** ✅ FEASIBLE
- Subscribe to raw telemetry → apply fault models → republish
- 5 fault types cover realistic degradation scenarios:
  - RF loss bursts
  - GNSS multipath (position jumps + HDOP spikes)
  - EKF unhealthy flags
  - Thrust shortfall symptoms
  - Battery sag curves
- Does NOT require real hardware simulation

**Group Planner Logic:** ⚠️ MODERATE COMPLEXITY
- Input: Group intent (mission, formation, constraints)
- Output: Per-drone plans with role-specific offsets/tasks
- Challenges:
  - Formation geometry calculations (LINE/WEDGE/BOX)
  - Role-based task assignment (LEADER coordinates, POINT_MAN advances, etc.)
  - Dynamic replanning on faults
- Mitigation: Start with static formations, add dynamic logic later

**Rules-Based AI:** ✅ FEASIBLE
- Threshold-based logic (telemetry → conditions → recommendations)
- No ML training required for MVP
- Upgrade path to ML-based AI preserved (same MQTT interface)

### 3.2 Safety Model Validation

**Advisory-Only Execution:** ✅ SAFE
- AI never publishes MAVLink commands directly
- Operator reviews recommendations via MQTT client
- Manual execution via Mission Planner (human approval gate)
- Hard constraints enforced:
  - No action when telemetry stale > threshold
  - No action below battery reserve
  - Never disable ArduPilot failsafes

**Upgrade Path (Optional v2):** Documented but out of MVP scope
- Approval-gated executor
- Command allow-list (HOLD/RTL only initially)
- Signed payloads + audit logs
- RBAC via MQTT ACLs

---

## 4. Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Fault injection doesn't match real ArduPilot behavior | Medium | Medium | Accept for MVP; validate with SITL later |
| Group planner state machine bugs | High | Medium | Comprehensive unit tests + test matrix |
| MQTT broker overload at scale (100+ drones) | Low | Low | Mosquitto handles this; add monitoring |
| Mission Planner integration friction | Low | High | Document manual workflow; MVP doesn't require automation |
| Windows Docker Desktop performance | Low | Low | Mosquitto is lightweight; test on target hardware |
| Schema validation failures in production | Medium | Low | jsonschema validation on all pub/sub; fail-fast |

---

## 5. Implementation Complexity Estimates

### 5.1 Core Components (Story Points using Fibonacci)

| Component | Complexity | Estimated SP | Rationale |
|-----------|------------|--------------|-----------|
| Docker compose + Mosquitto config | Low | **1** | 20 lines YAML, standard config |
| `fault_injector.py` | Medium | **5** | 200 lines, 5 fault models, MQTT sub/pub logic |
| `group_planner.py` (complete) | High | **8** | 300+ lines, formation math, role assignment |
| `simple_rules_ai.py` (complete) | Medium | **5** | 250 lines, threshold logic, 5 recommendation types |
| `asset_simulator.py` (complete) | Low | **3** | 150 lines, moving asset feed for ESCORT |
| Integration tests (fault injection) | Medium | **5** | Test matrix with 5 fault scenarios |
| End-to-end demo runbook | Low | **2** | Documentation + manual testing |
| Config examples & fleet setup | Low | **2** | Fleet configs already exist, need validation |

**Total Estimated:** 31 SP

**Velocity Assumptions:**
- Solo developer: ~8-10 SP/week (2-week sprint)
- Estimated completion: **2 sprints** (4 weeks)

### 5.2 Dependency Chain

**Critical Path:**
1. Docker compose + broker setup (SP: 1) → **Sprint 1, Day 1**
2. Complete `fault_injector.py` (SP: 5) → **Sprint 1, Days 2-4**
3. Complete `group_planner.py` (SP: 8) → **Sprint 1-2, Days 5-10**
4. Complete `simple_rules_ai.py` (SP: 5) → **Sprint 2, Days 11-13**
5. Integration tests (SP: 5) → **Sprint 2, Days 13-14**
6. End-to-end demo (SP: 2) → **Sprint 2, Day 14**

**Parallel Workstreams:**
- `asset_simulator.py` completion (SP: 3) can run parallel with planner work
- Config examples (SP: 2) can run parallel with AI work

---

## 6. External Blockers & Prerequisites

### 6.1 User Environment Setup

**Required (before implementation):**
- ✅ Docker Desktop installed on Windows
- ✅ Python 3.11+ with venv capability
- ✅ Git installed (already confirmed)
- ✅ GitHub CLI authenticated (already confirmed)

**Optional (for Mission Planner demos):**
- ⚠️ Mission Planner installed (Windows)
- ⚠️ ArduPilot SITL environment (can be deferred to post-MVP)

### 6.2 No External API Dependencies

- ✅ All processing is local (no cloud APIs)
- ✅ No external authentication required
- ✅ No rate limits or quotas to manage

---

## 7. Alternative Approaches Considered

### 7.1 DDS/ROS2 Instead of MQTT
**Rejected:** Overkill for MVP
- ROS2 adds complexity (build system, message generation)
- MQTT is simpler, more transparent for debugging
- Upgrade path: MQTT-DDS bridge exists if needed later

### 7.2 MAVLink Direct Integration
**Rejected for MVP:** Violates safety constraints
- MVP must be advisory-only (per requirements)
- MAVLink execution requires approval gates (out of scope)
- Future: Add MAVLink executor behind human approval

### 7.3 Real Physics Simulation (Gazebo/JSBSim)
**Rejected:** Not required for MVP
- No real hardware testing in scope
- Telemetry patterns can be modeled without physics
- SITL integration is post-MVP (optional demo)

---

## 8. Success Criteria Mapping

| Acceptance Criterion | Implementation Requirement | Risk |
|---------------------|---------------------------|------|
| Fleet monitoring (20+ drones) | `fleet_simulator.py` + Mosquitto | LOW ✅ |
| Roles & groups (5 roles, group G01) | `group_planner.py` + config files | MEDIUM ⚠️ |
| 3 mission types (PATROL/ESCORT/PERIMETER_GUARD) | Intent schemas + planner logic | MEDIUM ⚠️ |
| Fault simulation (5 fault types) | `fault_injector.py` + test matrix | MEDIUM ⚠️ |
| AI recommendations with evidence | `simple_rules_ai.py` + recommendation schema | LOW ✅ |
| Operator ACK workflow | ACK schema + MQTT pub/sub | LOW ✅ |
| Mission Planner integration | Manual demo workflow | LOW (manual) ⚠️ |

---

## 9. Recommendation

**✅ PROCEED WITH IMPLEMENTATION**

**Rationale:**
1. All dependencies are mature and available
2. Architecture is proven (MQTT pub/sub for IoT)
3. MVP scope is realistic (advisory-only, no hardware)
4. Estimated effort (31 SP / 2 sprints) is manageable
5. Risk profile is acceptable (no high-severity blockers)

**Suggested Approach:**
1. Start with infrastructure (Docker, broker, schemas) → **Week 1**
2. Build simulators + fault injector → **Week 1-2**
3. Implement planner + AI logic → **Week 2-3**
4. Integration testing + demo runbook → **Week 4**

**Next Step:** Create implementation plan with work breakdown into Stories
