# 📖 Story: Phase 1.2 - Implement 4 Additional Fault Models

**Parent:** Epic #1 - MVP Tech Stack PoC (Drone Fleet Ops)  
**State:** Idea  
**Created:** 2026-01-31  
**Analysis Source:** POC_PROGRESS_ANALYSIS.md (63% complete on original POC goals)

---

## Description

Complete the fault injection mechanism by implementing 4 additional fault models (GNSS multipath, EKF unhealthy, thrust shortfall, battery sag) following the established TDD + Hexagonal Architecture pattern. This closes the gap from 1/5 to 5/5 fault types and brings POC to 80% completion.

**Current State:**
- ✅ RF_LOSS_BURST implemented and tested (1/5 faults)
- ✅ FaultModel interface + Registry pattern established
- ✅ MQTT integration working (50 messages/demo validated)
- ⏳ **4 additional faults needed** to complete demo

**Why This Matters:**
- Original POC goal requires 5+ fault types for realistic fleet simulation
- Current demo shows only RF loss; operators need to see diverse failure modes
- Architecture proven; implementation is straightforward extension of RF_LOSS_BURST pattern
- Positions us for Phase 2 (planner + AI integration) which depends on rich fault events

---

## Acceptance Criteria

1. [ ] GNSS_MULTIPATH fault model implemented with configurable position offset and recovery timing
2. [ ] EKF_UNHEALTHY fault model implemented with configurable sensor quality degradation
3. [ ] THRUST_SHORTFALL fault model implemented with configurable performance reduction (%)
4. [ ] BATTERY_SAG fault model implemented with configurable voltage drop pattern
5. [ ] All 4 faults registered in FaultModelRegistry with correct names
6. [ ] Comprehensive unit tests for each fault (4+ tests per fault, following RF_LOSS_BURST pattern)
7. [ ] Integration demo updated to show all 5 faults being injected across fleet
8. [ ] MQTT schema documentation updated to include all 5 fault event types
9. [ ] No existing tests broken (22/22 unit tests still passing)
10. [ ] All code committed and PR ready for review

---

## Success Criteria

| Acceptance Criterion | Test Approach | Evidence Location |
|-------------|---------------|------------------|
| GNSS_MULTIPATH implemented | Unit test: offset calculation, recovery timing | `poc/tests/unit/test_gnss_multipath.py` |
| EKF_UNHEALTHY implemented | Unit test: sensor quality degradation, detection | `poc/tests/unit/test_ekf_unhealthy.py` |
| THRUST_SHORTFALL implemented | Unit test: performance reduction math, timing | `poc/tests/unit/test_thrust_shortfall.py` |
| BATTERY_SAG implemented | Unit test: voltage drop pattern, recovery | `poc/tests/unit/test_battery_sag.py` |
| All 4 faults in Registry | Unit test: registry lookup, instantiation | `poc/tests/unit/test_fault_registry.py` (expanded) |
| Unit tests comprehensive | All 4 tests: ~6 tests each, 100% coverage | `poc/tests/unit/test_*.py` (new) |
| Integration demo updated | Run demo: 50 messages with all 5 faults visible | `integration/demo_mqtt.py` (updated) |
| MQTT schema updated | Documentation: All 5 fault event types listed | `poc/docs/MQTT_SCHEMA.md` |
| No regressions | Run pytest: 22+ tests passing, <0.05s | `pytest poc/tests/unit -v` |
| Commit & PR ready | GitHub: Branch pushed, PR template ready | `feature/01-phase-1.2-fault-models` |

---

## Non-Goals (Out of Scope)

- Mission Planner integration (Phase 3+)
- Planner/AI integration (Phase 2)
- Dashboard implementation (optional)
- Real drone testing (Phase 4+)
- Performance optimization (defer to Phase 2)
- Fault prediction ML models (Phase 3+)

---

## Technical Notes

### Implementation Pattern

Follow RF_LOSS_BURST pattern (already proven):

```python
# From rf_loss_burst.py (existing):
class RFLossBurstFault(FaultModel):
    def __init__(self, burst_rate: float = 0.3):
        self.burst_rate = burst_rate
        self.burst_active = False
        self.burst_start_time = None

    def apply(self, telemetry: Telemetry) -> Optional[Telemetry]:
        """Simulate RF loss as message drops (None return)."""
        if random.random() < self.burst_rate:
            self.burst_active = True
            self.burst_start_time = time.time()

        if self.burst_active:
            if time.time() - self.burst_start_time > 2.0:
                self.burst_active = False
                return telemetry
            return None  # Drop message

        return telemetry
```

### Fault Specifications

#### 1. GNSS_MULTIPATH

- **Behavior:** Offset position by ±5-15m (configurable) for duration, then recover
- **Detection:** Position delta > threshold
- **Parameters:** offset_range, duration_sec, recovery_sec
- **Realism:** Common in urban canyons, tunnels

```python
class GNSSMultipathFault(FaultModel):
    def __init__(self, offset_range: float = 10.0, duration_sec: float = 5.0):
        self.offset_range = offset_range
        self.duration_sec = duration_sec
        self.fault_active = False
        self.fault_start = None
        self.offset_applied = None

    def apply(self, telemetry: Telemetry) -> Optional[Telemetry]:
        # Activate fault with 10% probability
        if not self.fault_active and random.random() < 0.1:
            self.fault_active = True
            self.fault_start = time.time()
            self.offset_applied = random.uniform(-self.offset_range, self.offset_range)

        # Check duration
        if self.fault_active:
            if time.time() - self.fault_start > self.duration_sec:
                self.fault_active = False
                return telemetry
            # Apply offset
            return Telemetry(
                position=Position(
                    lat=telemetry.position.lat + self.offset_applied / 111000,
                    lon=telemetry.position.lon + self.offset_applied / 111000
                ),
                battery=telemetry.battery
            )

        return telemetry
```

#### 2. EKF_UNHEALTHY

- **Behavior:** Degrade sensor quality (increase covariance), then recover
- **Detection:** EKF status field changes
- **Parameters:** quality_degradation_factor, duration_sec
- **Realism:** Sensor fusion failures in magnetic interference areas

#### 3. THRUST_SHORTFALL

- **Behavior:** Reduce effective thrust by N% for duration
- **Detection:** Altitude change slower than expected
- **Parameters:** reduction_percent, duration_sec
- **Realism:** ESC/motor degradation, battery voltage sag

#### 4. BATTERY_SAG

- **Behavior:** Voltage sags under load, recovers when idle
- **Detection:** Battery voltage anomaly
- **Parameters:** sag_voltage_drop, duration_sec
- **Realism:** Aging battery cells, high discharge rates

### Test Strategy (for each fault)

1. **Test instantiation** - Fault created with defaults/custom params
2. **Test activation** - Fault activates within expected timeframe
3. **Test effect** - Fault changes telemetry appropriately
4. **Test recovery** - Fault clears after duration
5. **Test multi-drone** - Multiple drones with independent fault state
6. **Test no-effect** - No fault → telemetry unchanged

### Files to Create/Modify

```
poc/src/domain/faults/
  ├── __init__.py                  # Export all fault models
  ├── gnss_multipath.py            # NEW (60 lines)
  ├── ekf_unhealthy.py             # NEW (50 lines)
  ├── thrust_shortfall.py          # NEW (55 lines)
  └── battery_sag.py               # NEW (50 lines)

poc/tests/unit/
  ├── test_gnss_multipath.py       # NEW (8 tests)
  ├── test_ekf_unhealthy.py        # NEW (8 tests)
  ├── test_thrust_shortfall.py     # NEW (8 tests)
  ├── test_battery_sag.py          # NEW (8 tests)
  └── test_fault_registry.py       # MODIFY: Add 4 new faults to registry tests

integration/
  └── demo_mqtt.py                 # MODIFY: Update to inject all 5 faults

poc/docs/
  └── MQTT_SCHEMA.md               # MODIFY: Document all 5 fault event types
```

---

## Dependencies

- [ ] #0 - N/A (Phase 1.1 PoC complete, RF_LOSS_BURST working)

**Blockers:** None  
**Depends On:** RF_LOSS_BURST implementation (✅ complete)

---

## Test Approach

### Unit Tests (Primary)
- 8 new test files (2 tests per fault minimum)
- Follow RF_LOSS_BURST test pattern from `test_rf_loss_burst.py`
- 100% code coverage for fault models
- Expected: 32 new tests + 6 registry tests = 38 new tests
- All tests < 0.05s runtime

### Integration Tests
- Updated `integration/demo_mqtt.py` to inject all 5 faults
- Expected: 50 messages with mixed faults visible
- Verify MQTT messages contain correct fault event types
- Manual inspection of MQTT.Cool client output

### Regression Testing
- Run `pytest poc/tests/unit -v`
- Verify existing 22 tests still pass
- Verify total test time < 0.10s

---

## Estimate

**Story Points:** 5 SP (same as Phase 1.1 PoC architecture)  
**Estimated Duration:** 3-4 days  
**Complexity:** Medium (pattern already proven)

**Breakdown:**
- GNSS_MULTIPATH: 1 SP (1 day)
- EKF_UNHEALTHY: 1 SP (1 day)
- THRUST_SHORTFALL: 1 SP (1 day)
- BATTERY_SAG: 1 SP (1 day)
- Integration + Testing + Docs: 1 SP (0.5 day)

---

## Definition of Ready Checklist

- [x] User story is clear and testable
- [x] Acceptance criteria are specific and measurable (10 criteria)
- [x] Dependencies identified and listed (none blocking)
- [x] Acceptance criteria linked to technical tasks (✅ all mapped)
- [x] Architect reviewed (hexagonal pattern established)
- [x] Estimated story points assigned (5 SP, 3-4 days)
- [x] Parent epic referenced (implicit: Phase 1.2 POC completion)
- [x] Analysis backing included (POC_PROGRESS_ANALYSIS.md)

---

## Definition of Done Checklist

**When this story is complete:**

- [ ] All 4 fault models implemented in `poc/src/domain/faults/`
- [ ] 32+ unit tests written and passing
- [ ] Existing 22 unit tests still passing (regression verified)
- [ ] `integration/demo_mqtt.py` updated to show all 5 faults
- [ ] `poc/docs/MQTT_SCHEMA.md` updated with all 5 fault event types
- [ ] `poc/src/domain/fault_registry.py` includes all 5 faults
- [ ] PR created with evidence mapping table
- [ ] PR linked: `Closes #<issue-id>`
- [ ] Code review approved by @nsin08 (CODEOWNER)
- [ ] All CI checks passing
- [ ] Merged to main

---

## PR Evidence Mapping (for Implementation Phase)

When story moves to In Review, PR will include:

| Acceptance Criterion | Test File | Evidence Line | Status |
|-----------|-----------|---------------|--------|
| GNSS_MULTIPATH implemented | `test_gnss_multipath.py` | L1-8 (all tests) | ✅ |
| EKF_UNHEALTHY implemented | `test_ekf_unhealthy.py` | L1-8 (all tests) | ✅ |
| THRUST_SHORTFALL implemented | `test_thrust_shortfall.py` | L1-8 (all tests) | ✅ |
| BATTERY_SAG implemented | `test_battery_sag.py` | L1-8 (all tests) | ✅ |
| All 4 in Registry | `test_fault_registry.py` | L45-70 (registry tests) | ✅ |
| Unit tests comprehensive | `poc/tests/unit/*.py` | All new files | ✅ |
| Integration demo updated | `integration/demo_mqtt.py` | L150-200 (fault injection) | ✅ |
| MQTT schema updated | `poc/docs/MQTT_SCHEMA.md` | All fault event types | ✅ |
| No regressions | CI logs | pytest output | ✅ |

---

## Handoff Notes

**From Architecture/PM:**

This story completes the Fault Injection subsystem and brings the POC from 63% → 80% completion (per original planned goals). It's a straightforward implementation sprint using proven patterns.

**Key Points for Implementer:**
1. Use TDD: Red-Green-Refactor for each fault
2. Follow RF_LOSS_BURST as template (already proven pattern)
3. Parallel implementation possible (all faults independent)
4. Can demo after 1-2 faults complete
5. Archive as `.context/sprint/` (committed, not git-ignored)

**Next Phase:**
After DoD complete → Phase 2 (Refactor & Integrate Planner + AI)

---

**Last Updated:** 2026-01-31 by @nsin08  
**Status Transition Tracking:**
- Idea → Approved (PM review)
- Approved → Ready (DoR checklist complete)
- Ready → In Progress (assign to implementer)
- In Progress → In Review (PR opened)
- In Review → Done (PR approved + merged)
- Done → Released (included in next release)
