# Implementation Plan: Drone Fleet Ops MVP (TDD + Hexagonal Architecture)

**Generated:** 2026-01-31 (TDD REVISION)  
**Project:** ai_drones  
**Approach:** Test-Driven Development + Hexagonal Architecture + Design Patterns  
**Duration:** 2 sprints (2 weeks)  
**Philosophy:** Incremental, verifiable, test-first

---

## Architecture Philosophy

### Hexagonal Architecture (Ports & Adapters)

**Goal:** Business logic independent of external systems (MQTT, file I/O, etc.)

```
┌─────────────────────────────────────────┐
│          External World                 │
│  (MQTT, Files, HTTP, Redis, etc.)      │
└──────────────┬──────────────────────────┘
               │ Adapters (implementations)
┌──────────────▼──────────────────────────┐
│            Ports (interfaces)           │
│  MessageBroker, ConfigLoader, etc.     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Domain Core (Pure Python)       │
│  Entities, Value Objects, Services     │
│  NO external dependencies              │
│  100% unit testable                    │
└─────────────────────────────────────────┘
```

**Benefits:**
- ✅ Test business logic without MQTT broker
- ✅ Swap MQTT for Kafka/Redis without touching domain
- ✅ Fast feedback (no I/O in tests)
- ✅ Clear separation of concerns

### Design Patterns

1. **Registry Pattern** - Dynamic registration of strategies
2. **Strategy Pattern** - Pluggable algorithms (faults, missions, rules)
3. **Factory Pattern** - Object creation with complex initialization
4. **Repository Pattern** - Abstract data access

---

## Project Structure (Refactored)

```
ai_drones/
├── src/
│   ├── domain/              # Core business logic (no external deps)
│   │   ├── entities/
│   │   │   ├── drone.py
│   │   │   ├── telemetry.py
│   │   │   └── group.py
│   │   ├── value_objects/
│   │   │   ├── position.py
│   │   │   ├── recommendation.py
│   │   │   └── plan.py
│   │   ├── services/
│   │   │   ├── fault_model.py      # Interface
│   │   │   ├── mission_planner.py  # Interface
│   │   │   └── rule_engine.py      # Interface
│   │   ├── registries/
│   │   │   ├── fault_registry.py
│   │   │   ├── mission_registry.py
│   │   │   └── rule_registry.py
│   │   └── faults/
│   │       ├── rf_loss_burst.py
│   │       ├── gnss_multipath.py
│   │       ├── ekf_unhealthy.py
│   │       ├── thrust_shortfall.py
│   │       └── battery_sag.py
│   ├── ports/               # Interfaces (contracts)
│   │   ├── message_broker.py
│   │   ├── config_loader.py
│   │   └── telemetry_repository.py
│   ├── adapters/            # External integrations
│   │   ├── mqtt_broker.py
│   │   ├── memory_broker.py    # For testing
│   │   ├── json_config.py
│   │   └── file_repository.py
│   └── apps/                # Application entry points
│       ├── fleet_simulator.py
│       ├── fault_injector.py
│       ├── group_planner.py
│       └── rules_ai.py
├── tests/
│   ├── unit/                # Fast, no I/O
│   │   ├── domain/
│   │   │   ├── test_telemetry.py
│   │   │   ├── test_rf_loss_burst.py
│   │   │   └── test_patrol_planner.py
│   │   └── adapters/
│   │       └── test_memory_broker.py
│   ├── integration/         # With real adapters
│   │   ├── test_mqtt_broker.py
│   │   └── test_fault_injection_pipeline.py
│   └── e2e/                 # Full system tests
│       └── test_patrol_mission.py
├── ops/
│   └── docker-compose.yml
└── docs/
    └── .context/project/docs/
```

---

## TDD Workflow (Red-Green-Refactor)

### Example: Implementing RF_LOSS_BURST Fault

**1. RED - Write failing test**
```python
# tests/unit/domain/test_rf_loss_burst.py
def test_drops_telemetry_during_burst():
    # Arrange
    config = {"every_sec": 180, "down_sec": 8}
    fault = RFLossBurstFault(config)
    telemetry = Telemetry(drone_id="D001", timestamp=time.time())
    
    # Simulate time into burst
    fault._last_burst["D001"] = time.time() - 5  # 5s into burst
    
    # Act
    result, faults = fault.apply(telemetry)
    
    # Assert
    assert result is None
    assert "RF_LOSS_BURST" in faults
```

**2. GREEN - Minimal implementation**
```python
# src/domain/faults/rf_loss_burst.py
class RFLossBurstFault(FaultModel):
    def apply(self, telemetry):
        # Minimal code to make test pass
        return None, ["RF_LOSS_BURST"]
```

**3. REFACTOR - Add real logic, more tests**
```python
def test_passes_telemetry_outside_burst():
    # Another test case
    pass

def test_starts_new_burst_after_interval():
    # Another test case
    pass
```

Repeat for every feature.

---

## Sprint 1: Core Architecture + Fault Injection (10 SP, 1 week)

### Phase 1.1: PoC - Fault Injection with Registry (2 SP, Day 1)

**Goal:** Working demo of hexagonal architecture with 1 fault model

**Deliverables:**
- ✅ Domain entities (Telemetry)
- ✅ FaultModel interface
- ✅ RFLossBurstFault (TDD)
- ✅ FaultModelRegistry
- ✅ MessageBroker port + InMemoryBroker adapter
- ✅ 100% unit test coverage
- ✅ Integration test with InMemoryBroker
- ✅ Runnable demo script

**Story 1.1.1: Core Domain Entities (TDD)**
- **SP:** 1
- **Tasks:**
  1. Write test for `Telemetry` value object
  2. Implement `Telemetry` (immutable, validation)
  3. Write test for `Position` value object
  4. Implement `Position`

**Example Test:**
```python
# tests/unit/domain/test_telemetry.py
def test_telemetry_creation():
    t = Telemetry(
        drone_id="D001",
        timestamp=1234567890.0,
        position=Position(lat=28.6139, lon=77.2090, alt_m=20.0),
        battery_pct=85.0
    )
    assert t.drone_id == "D001"
    assert t.battery_pct == 85.0

def test_telemetry_immutable():
    t = Telemetry(drone_id="D001", ...)
    with pytest.raises(AttributeError):
        t.drone_id = "D002"  # Should fail
```

**Story 1.1.2: Fault Model Interface + Registry (TDD)**
- **SP:** 1
- **Tasks:**
  1. Write test for `FaultModelRegistry`
  2. Implement `FaultModelRegistry.register()` and `.create()`
  3. Write test for `RFLossBurstFault`
  4. Implement `RFLossBurstFault.apply()`
  5. Integration test: Register + create + apply

**Example Test:**
```python
# tests/unit/domain/test_fault_registry.py
def test_register_and_create_fault():
    registry = FaultModelRegistry()
    registry.register("RF_LOSS_BURST", RFLossBurstFault)
    
    fault = registry.create("RF_LOSS_BURST", {"every_sec": 180, "down_sec": 8})
    
    assert isinstance(fault, RFLossBurstFault)
    assert fault.every_sec == 180
```

**Demo Output:**
```bash
python poc/demo_fault_injection.py

[PoC] Creating fault registry...
[PoC] Registering RF_LOSS_BURST fault model...
[PoC] Publishing 10 telemetry messages...
[PoC] Message 1: PASSED (no fault)
[PoC] Message 2: PASSED (no fault)
[PoC] Message 3: DROPPED (RF_LOSS_BURST active)
[PoC] Message 4: DROPPED (RF_LOSS_BURST active)
[PoC] Message 5: PASSED (burst ended)
...
[PoC] ✅ Demo complete. Fault injection working!
```

---

### Phase 1.2: Complete Fault Models (3 SP, Days 2-3)

**Story 1.2.1: GNSS Multipath Fault (TDD)**
- Write tests for position jumps + HDOP spikes
- Implement `GNSSMultipathFault`
- Register in registry

**Story 1.2.2: EKF Unhealthy Fault (TDD)**
- Write tests for EKF flags
- Implement `EKFUnhealthyFault`

**Story 1.2.3: Thrust Shortfall + Battery Sag Faults (TDD)**
- Write tests
- Implement both faults
- All 5 faults registered and testable

---

### Phase 1.3: MQTT Adapter + Integration (2 SP, Day 4)

**Story 1.3.1: MessageBroker Port (Interface)**
```python
# src/ports/message_broker.py
class MessageBroker(ABC):
    @abstractmethod
    def publish(self, topic: str, payload: dict):
        pass
    
    @abstractmethod
    def subscribe(self, topic: str, callback: Callable):
        pass
```

**Story 1.3.2: MQTTBrokerAdapter (TDD)**
- Write test with mock paho-mqtt client
- Implement adapter
- Integration test with real Mosquitto

**Story 1.3.3: Fault Injector App (Composition Root)**
```python
# src/apps/fault_injector.py
def main():
    # Composition root - wire dependencies
    broker = MQTTBrokerAdapter("localhost", 1883)
    config = JsonConfigLoader("config.json")
    
    registry = FaultModelRegistry()
    registry.register("RF_LOSS_BURST", RFLossBurstFault)
    registry.register("GNSS_MULTIPATH", GNSSMultipathFault)
    # ... register all faults
    
    injector = FaultInjector(broker, registry, config)
    injector.run()
```

---

### Phase 1.4: Fleet Simulator Refactor (3 SP, Day 5)

**Story 1.4.1: Extract Domain Logic from Simulator**
- Separate drone state management from MQTT
- Use MessageBroker port
- 100% unit testable (no MQTT in tests)

**Story 1.4.2: DroneFactory Pattern**
```python
# src/domain/factories/drone_factory.py
class DroneFactory:
    @staticmethod
    def create_fleet(count: int, base_position: Position) -> List[Drone]:
        return [
            Drone(
                id=f"D{i:03d}",
                position=base_position.offset_random(100),
                battery_pct=100.0
            )
            for i in range(1, count + 1)
        ]
```

---

## Sprint 2: Mission Planning + AI + Integration (11 SP, 1 week)

### Phase 2.1: Mission Planning with Strategy Pattern (5 SP, Days 1-3)

**Story 2.1.1: MissionPlanner Interface + Registry (TDD)**
```python
# src/domain/services/mission_planner.py
class MissionPlanner(ABC):
    @abstractmethod
    def plan(self, intent: Intent, group: Group) -> Plan:
        pass

# src/domain/registries/mission_registry.py
class MissionPlannerRegistry:
    def register(self, mission_type: str, planner_class: Type[MissionPlanner]):
        self._planners[mission_type] = planner_class
```

**Story 2.1.2: PatrolPlanner Strategy (TDD)**
- Write tests for polygon patrol logic
- Write tests for formation geometry
- Implement PatrolPlanner
- Unit tests (no MQTT, no external deps)

**Story 2.1.3: EscortPlanner Strategy (TDD)**
- Write tests for asset tracking
- Write tests for formation around moving target
- Implement EscortPlanner

**Story 2.1.4: PerimeterGuardPlanner Strategy (TDD)**
- Write tests for sector assignment
- Implement PerimeterGuardPlanner

**Story 2.1.5: GroupPlanner App (Composition Root)**
- Wire dependencies
- Integration test with InMemoryBroker
- Integration test with MQTTBroker

---

### Phase 2.2: Rules AI with Strategy Pattern (3 SP, Day 4)

**Story 2.2.1: Rule Interface + Registry (TDD)**
```python
# src/domain/services/rule_engine.py
class Rule(ABC):
    @abstractmethod
    def evaluate(self, telemetry: Telemetry) -> Optional[Recommendation]:
        pass

# src/domain/registries/rule_registry.py
class RuleRegistry:
    def register(self, rule_name: str, rule_class: Type[Rule]):
        self._rules[rule_name] = rule_class
```

**Story 2.2.2: Implement 3 Rules (TDD)**
- `LowBatteryRule`
- `EKFUnhealthyRule`
- `RFLossBurstRule`

**Story 2.2.3: RulesAI App (Composition Root)**
- Wire dependencies
- Integration test

---

### Phase 2.3: Integration Testing (3 SP, Day 5)

**Story 2.3.1: Fault Injection Test Matrix**
- 5 integration tests (1 per fault)
- Verify events published
- Verify AI recommendations triggered

**Story 2.3.2: Mission Planning Integration Tests**
- 3 integration tests (1 per mission type)
- Verify plans published
- Verify role assignments correct

**Story 2.3.3: End-to-End Test**
- Full pipeline: simulator → injector → planner → AI
- Verify PATROL mission with RF_LOSS_BURST fault
- Verify AI recommendation triggered

---

## Test Coverage Requirements

| Layer | Coverage Target | Test Type |
|-------|----------------|-----------|
| Domain (entities, services) | **100%** | Unit tests only |
| Ports (interfaces) | **100%** | Unit tests (mocks) |
| Adapters | **80%** | Integration tests |
| Apps | **60%** | Integration + E2E |

**Rationale:** Domain is pure logic (easy to test 100%). Adapters have I/O (harder to test exhaustively).

---

## Definition of Done (Per Story)

- [ ] Tests written **before** implementation (TDD)
- [ ] All tests passing (`pytest` green)
- [ ] Code coverage ≥ target for layer
- [ ] No `# type: ignore` (full type hints)
- [ ] Docstrings for public APIs
- [ ] Integration test with InMemoryBroker (unit-like speed)
- [ ] Integration test with real adapter (if applicable)
- [ ] PR opened with evidence mapping

---

## Tools & Setup

### Testing Tools
```bash
pip install pytest pytest-cov pytest-asyncio
pip install mypy  # Type checking
pip install black flake8  # Formatting + linting
```

### Run Tests
```bash
# Unit tests only (fast, no I/O)
pytest tests/unit -v

# Integration tests (requires Docker for MQTT)
docker compose -f ops/docker-compose.yml up -d
pytest tests/integration -v

# E2E tests (full system)
pytest tests/e2e -v

# Coverage report
pytest --cov=src --cov-report=html
```

---

## PoC Acceptance Criteria

**PoC is complete when:**
- [ ] Can run `python poc/demo_fault_injection.py` successfully
- [ ] Demo shows telemetry being dropped during RF burst
- [ ] All unit tests pass (`pytest tests/unit -v`)
- [ ] Test coverage = 100% for domain layer
- [ ] Zero external dependencies in domain/ (only stdlib + pydantic/dataclasses)
- [ ] Can swap InMemoryBroker ↔ MQTTBroker without changing domain code

---

## Benefits Over Original Plan

| Aspect | Original | TDD + Hexagonal |
|--------|----------|----------------|
| **Confidence** | Low (test at end) | High (test at every step) |
| **Feedback** | Slow (need MQTT) | Fast (in-memory tests) |
| **Debugging** | Hard (integration bugs) | Easy (isolated units) |
| **Extensibility** | Modify existing code | Register new strategies |
| **Testability** | Need real MQTT | Mock/in-memory broker |
| **Refactoring** | Risky (break unknowns) | Safe (tests protect) |
| **Onboarding** | Read 700 lines | Read tests (specs) |

---

## Next Immediate Actions

1. **Create PoC directory structure** (10 min)
2. **Write first failing test** (Telemetry entity) (5 min)
3. **Make test pass** (implement Telemetry) (10 min)
4. **Write second test** (RFLossBurstFault) (10 min)
5. **Repeat cycle** until PoC demo works (2 hours total)
6. **Demo to stakeholders** → get feedback → iterate

---

**Document Owner:** @nsin08  
**Status:** ✅ Ready to Begin PoC  
**Next Review:** After PoC Demo (Day 1 end)
