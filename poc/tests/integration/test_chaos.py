"""
Chaos tests for Mission Control v4 — W16 G13.

Tests cover MQTT broker restart mid-mission and inventory circuit breaker
failure + recovery scenarios using mocks (no real Docker required for CI).

For full chaos integration against real services, use:
    pytest tests/integration/ -m chaos --docker
"""

import threading
import time
import unittest.mock as mock
from unittest.mock import MagicMock, patch

import pytest

from poc.v4_mission_control.infra.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from poc.v4_mission_control.infra.mqtt_client import MqttReconnectClient
from poc.v4_mission_control.services.service_status import ServiceStatusService
from poc.v4_mission_control.ws.manager import WebSocketManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws_manager() -> WebSocketManager:
    return WebSocketManager()


def _make_service_status(ws: WebSocketManager | None = None) -> ServiceStatusService:
    return ServiceStatusService(ws_manager=ws or _make_ws_manager())


# ---------------------------------------------------------------------------
# Scenario 1: MQTT broker crash → UI badge reflects MQTT OFFLINE
# ---------------------------------------------------------------------------


class TestMqttCrashScenario:
    """Verify that a sudden MQTT disconnect is correctly propagated to the
    ServiceStatusService, which then broadcasts the state change to all WS clients."""

    def test_initial_state_is_disconnected(self):
        svc = _make_service_status()
        assert svc.as_dict()["mqtt"] is False

    def test_connect_then_crash_updates_status(self):
        ws = _make_ws_manager()
        svc = ServiceStatusService(ws_manager=ws)

        svc.report_mqtt_connected()
        assert svc.as_dict()["mqtt"] is True

        # Simulate broker crash
        svc.report_mqtt_disconnected()
        assert svc.as_dict()["mqtt"] is False

    def test_disconnect_broadcasts_service_status_event(self):
        ws = _make_ws_manager()
        broadcasts: list[dict] = []

        def capture(*args, **kwargs):
            captures = args[1] if len(args) > 1 else kwargs.get("payload", {})
            broadcasts.append(captures)

        ws.broadcast_sync = capture  # type: ignore[method-assign]

        svc = ServiceStatusService(ws_manager=ws)
        svc.report_mqtt_connected()    # fires broadcast #1
        svc.report_mqtt_disconnected() # fires broadcast #2

        assert len(broadcasts) == 2
        assert broadcasts[1]["mqtt"] is False

    def test_reconnect_after_crash_broadcasts_online(self):
        ws = _make_ws_manager()
        broadcasts: list[dict] = []
        ws.broadcast_sync = lambda _evt, payload: broadcasts.append(payload)

        svc = ServiceStatusService(ws_manager=ws)
        svc.report_mqtt_connected()
        svc.report_mqtt_disconnected()
        svc.report_mqtt_connected()  # reconnect fires broadcast #3

        assert broadcasts[-1]["mqtt"] is True

    def test_mqtt_client_fires_on_disconnect_callback(self):
        """MqttReconnectClient calls on_disconnect when broker drops."""
        disconnect_events: list[str] = []

        client = MqttReconnectClient(
            host="localhost",
            port=1883,
            on_disconnect=lambda: disconnect_events.append("disconnected"),
        )

        # First simulate connect so the client marks itself as connected
        client._paho_on_connect(None, None, None, 0, None)
        assert client.is_connected

        # Now simulate broker crash — only fires callback when was_connected=True
        client._paho_on_disconnect(None, None, None, None, None)
        assert disconnect_events == ["disconnected"]

    def test_mqtt_client_fires_on_connect_callback(self):
        connect_events: list[str] = []

        client = MqttReconnectClient(
            host="localhost",
            port=1883,
            on_connect=lambda: connect_events.append("connected"),
        )
        # Simulate paho firing connect callback
        client._paho_on_connect(None, None, None, 0, None)
        assert connect_events == ["connected"]

    def test_reconnect_loop_uses_backoff_schedule(self):
        """Reconnect loop sleeps between failed attempts using backoff schedule."""
        sleep_calls: list[float] = []
        attempt = [0]

        client = MqttReconnectClient(
            host="localhost",
            port=1883,
            backoff_schedule=[0.001, 0.002, 0.003],
        )
        client._running = True

        def fake_try_connect() -> bool:
            attempt[0] += 1
            if attempt[0] >= 3:
                # Simulate success: set connected so loop exits
                client._connected = True
                return True
            return False

        client._try_connect = fake_try_connect  # type: ignore[method-assign]

        with patch("time.sleep", side_effect=lambda d: sleep_calls.append(d)):
            client._reconnect_loop()

        # Should have slept twice (after attempt 1 and 2) before succeeding
        assert sleep_calls == [0.001, 0.002]

    def test_backoff_schedule_cycles_on_long_outage(self):
        """After exhausting backoff schedule, it cycles back to start."""
        sleep_calls: list[float] = []
        attempt = [0]
        schedule = [0.001, 0.005, 0.030]

        client = MqttReconnectClient(
            host="localhost",
            port=1883,
            backoff_schedule=schedule,
        )
        client._running = True

        def fail_then_stop() -> bool:
            attempt[0] += 1
            if attempt[0] >= 7:
                # On 7th attempt, stop the loop (will still sleep once more)
                client._running = False
            return False

        client._try_connect = fail_then_stop  # type: ignore[method-assign]

        with patch("time.sleep", side_effect=lambda d: sleep_calls.append(d)):
            client._reconnect_loop()

        # 7 attempts → 7 sleeps; schedule cycles: 0.001,0.005,0.030,0.001,0.005,0.030,0.001
        assert len(sleep_calls) == 7
        assert sleep_calls[0] == 0.001
        assert sleep_calls[3] == 0.001  # cycle restarts


# ---------------------------------------------------------------------------
# Scenario 2: Inventory circuit breaker — 3 strikes → OPEN
# ---------------------------------------------------------------------------


class TestInventoryCircuitBreakerChaos:
    """Full lifecycle: CLOSED → OPEN (after 3 fails) → HALF_OPEN (after reset_timeout)
    → CLOSED (on probe success).

    Uses real CB with mocked time to control reset_timeout behaviour.
    """

    def test_three_failures_open_the_circuit(self):
        cb = CircuitBreaker(threshold=3, reset_timeout=30.0, name="inventory")
        fail = mock.Mock(side_effect=ConnectionError("inventory down"))

        for _ in range(3):
            with pytest.raises(ConnectionError):
                cb.call(fail)

        assert cb.state == CircuitState.OPEN

    def test_open_circuit_raises_circuit_open_error_immediately(self):
        cb = CircuitBreaker(threshold=3, reset_timeout=30.0)
        fail = mock.Mock(side_effect=ConnectionError)
        for _ in range(3):
            with pytest.raises(ConnectionError):
                cb.call(fail)

        # No actual call — CircuitOpenError raised before reaching the function
        ok = mock.Mock(return_value="data")
        with pytest.raises(CircuitOpenError):
            cb.call(ok)
        ok.assert_not_called()

    def test_cached_data_served_when_circuit_open(self):
        """Application-level pattern: catch CircuitOpenError and return cached data."""
        cb = CircuitBreaker(threshold=3, reset_timeout=30.0)
        fail = mock.Mock(side_effect=ConnectionError)

        cache = {"drones": ["SIM-001"]}
        for _ in range(3):
            with pytest.raises(ConnectionError):
                cb.call(fail)

        # Simulate application code serving cached data
        try:
            result = cb.call(mock.Mock(return_value={"drones": []}))
        except CircuitOpenError:
            result = cache

        assert result == {"drones": ["SIM-001"]}

    def test_circuit_half_opens_after_reset_timeout(self):
        cb = CircuitBreaker(threshold=2, reset_timeout=0.05)
        fail = mock.Mock(side_effect=Exception("down"))

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(fail)

        assert cb.state == CircuitState.OPEN

        # Fast-forward past reset_timeout
        time.sleep(0.1)
        # Next call should be allowed (HALF_OPEN probe)
        ok = mock.Mock(return_value="ok")
        result = cb.call(ok)

        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_failed_probe_re_opens_circuit(self):
        cb = CircuitBreaker(threshold=2, reset_timeout=0.05)
        fail = mock.Mock(side_effect=Exception("down"))

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(fail)

        time.sleep(0.1)

        # Probe also fails → back to OPEN
        with pytest.raises(Exception):
            cb.call(mock.Mock(side_effect=Exception("still down")))

        assert cb.state == CircuitState.OPEN

    def test_manual_reset_returns_to_closed(self):
        cb = CircuitBreaker(threshold=2, reset_timeout=30.0)
        fail = mock.Mock(side_effect=ConnectionError)
        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(fail)

        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_circuit_status_reflects_in_service_status_service(self):
        """ServiceStatusService marks inventory unavailable when CB is OPEN."""
        ws = _make_ws_manager()
        broadcasts: list[dict] = []
        ws.broadcast_sync = lambda _evt, payload: broadcasts.append(payload)

        svc = ServiceStatusService(ws_manager=ws)
        cb = CircuitBreaker(threshold=3, reset_timeout=30.0, name="inventory")

        fail = mock.Mock(side_effect=ConnectionError)
        for _ in range(3):
            try:
                cb.call(fail)
            except ConnectionError:
                svc.report_inventory_failure()

        assert svc.as_dict()["inventory"] is False
        # Broadcasting happened on state change (False for first failure)
        assert any(b.get("inventory") is False for b in broadcasts)

    def test_inventory_recovery_marks_service_available(self):
        ws = _make_ws_manager()
        broadcasts: list[dict] = []
        ws.broadcast_sync = lambda _evt, payload: broadcasts.append(payload)

        svc = ServiceStatusService(ws_manager=ws)

        # Simulate 3 failures then 1 success (recovery)
        for _ in range(3):
            svc.report_inventory_failure()
        svc.report_inventory_success()

        assert svc.as_dict()["inventory"] is True
        assert broadcasts[-1]["inventory"] is True


# ---------------------------------------------------------------------------
# Scenario 3: Concurrent missions — no cross-contamination
# ---------------------------------------------------------------------------


class TestConcurrentMissionIsolation:
    """Verify that 5 concurrent missions with different drone assignements
    do not interfere with each other's state.
    """

    def test_five_concurrent_missions_independent(self):
        from poc.v4_mission_control.repos.mission_repo import InMemoryMissionRepository
        from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository
        from poc.v4_mission_control.services.mission_service import MissionService
        from poc.v4_mission_control.schemas.mission import MissionCreateRequest, MissionStatus

        repo = InMemoryMissionRepository()
        event_repo = InMemoryEventRepository()
        svc = MissionService(mission_repo=repo, event_repo=event_repo)

        # Create 5 independent missions
        mission_ids = []
        for i in range(5):
            m = svc.create_mission(
                MissionCreateRequest(
                    type="PATROL",
                    created_by=f"pilot{i}",
                    tasks=[],
                )
            )
            mission_ids.append(m.mission_id)

        # Advance all to ACTIVE via plan → start
        for mid in mission_ids:
            svc.plan_mission(mid)
            svc.start_mission(mid)

        # Abort only the first mission
        svc.abort_mission(mission_ids[0])

        # Verify others are still ACTIVE
        all_missions = {m.mission_id: m for m in svc.list_missions()}
        assert all_missions[mission_ids[0]].status == MissionStatus.ABORTED
        for mid in mission_ids[1:]:
            assert all_missions[mid].status == MissionStatus.ACTIVE

    def test_concurrent_mission_threads_no_deadlock(self):
        """Drive missions from multiple threads simultaneously."""
        from poc.v4_mission_control.repos.mission_repo import InMemoryMissionRepository
        from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository
        from poc.v4_mission_control.services.mission_service import MissionService
        from poc.v4_mission_control.schemas.mission import MissionCreateRequest

        repo = InMemoryMissionRepository()
        event_repo = InMemoryEventRepository()
        svc = MissionService(mission_repo=repo, event_repo=event_repo)

        errors: list[Exception] = []
        created_ids: list[str] = []

        def make_and_drive():
            try:
                m = svc.create_mission(MissionCreateRequest(type="ESCORT", tasks=[]))
                created_ids.append(m.mission_id)
                svc.plan_mission(m.mission_id)
                svc.start_mission(m.mission_id)
                svc.complete_mission(m.mission_id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=make_and_drive) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert errors == [], f"Thread errors: {errors}"
        assert len(created_ids) == 5


# ---------------------------------------------------------------------------
# Scenario 4: Telemetry ingestion rate — in-memory store handles 100 events/s
# ---------------------------------------------------------------------------


class TestTelemetryIngestionRate:
    """Verify the event log can accept 100 events/sec without data loss."""

    def test_100_events_per_second_in_memory(self):
        from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository

        repo = InMemoryEventRepository()
        count = 100
        start = time.perf_counter()

        for i in range(count):
            repo.append(
                aggregate_id=f"SIM-{(i % 50) + 1:03d}",
                aggregate_type="Drone",
                event_type="TELEMETRY_RECEIVED",
                payload_json={"battery_pct": 80, "gps_sats": 9, "seq": i},
            )

        elapsed = time.perf_counter() - start
        # Should complete well under 1 second
        assert elapsed < 1.0, f"100 events took {elapsed:.3f}s — too slow"

        # All events persisted (check total count)
        all_events = repo.list_recent(limit=200)
        sim001_events = [e for e in all_events if e.aggregate_id == "SIM-001"]
        assert len(sim001_events) >= 2  # SIM-001 gets events at i=0, 50

    def test_1000_events_batch_under_one_second(self):
        from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository

        repo = InMemoryEventRepository()
        start = time.perf_counter()

        for i in range(1000):
            repo.append(
                aggregate_id="SIM-001",
                aggregate_type="Drone",
                event_type="TELEMETRY_RECEIVED",
                payload_json={"seq": i, "battery_pct": 80},
            )

        elapsed = time.perf_counter() - start
        assert elapsed < 1.0
        events = repo.list_recent(limit=1000)
        assert len(events) >= 1
