"""Unit tests: MqttReconnectClient backoff schedule — W15 G11.

These tests mock paho and time.sleep so no real broker is needed.

Coverage:
  - connect() calls _try_connect; on success is_connected becomes True
  - connect() on failure starts reconnect loop
  - reconnect loop fires with correct backoff delays cycling [1, 5, 30, 1, ...]
  - reconnect loop stops when _running=False
  - reconnect loop stops when already connected
  - on_connect callback is called after successful connection
  - on_disconnect callback is called when paho fires disconnect
  - ServiceStatusService is notified via callbacks
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, call, patch

import pytest

from poc.v4_mission_control.infra.mqtt_client import (
    DEFAULT_BACKOFF_SCHEDULE,
    MqttReconnectClient,
)
from poc.v4_mission_control.services.service_status import ServiceStatusService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(**kwargs) -> MqttReconnectClient:
    defaults = dict(host="localhost", port=1883)
    defaults.update(kwargs)
    return MqttReconnectClient(**defaults)


# ---------------------------------------------------------------------------
# connect() — successful first attempt
# ---------------------------------------------------------------------------


class TestConnect:
    @patch("poc.v4_mission_control.infra.mqtt_client._paho.Client")
    def test_connect_success_sets_is_connected(self, MockPaho):
        instance = MockPaho.return_value
        instance.connect.return_value = None  # no exception
        instance.loop_start.return_value = None

        c = _client()
        c._client = instance

        # Simulate paho calling on_connect callback immediately
        def fake_connect(host, port):
            c._paho_on_connect(instance, None, None, 0, None)

        instance.connect.side_effect = fake_connect
        c.connect()
        assert c.is_connected is True

    @patch("poc.v4_mission_control.infra.mqtt_client._paho.Client")
    def test_connect_failure_starts_reconnect_loop(self, MockPaho):
        instance = MockPaho.return_value
        instance.connect.side_effect = ConnectionRefusedError("broker down")

        c = _client()
        c._client = instance

        # Override start_reconnect_loop to avoid spawning thread
        loop_started = threading.Event()
        original = c.start_reconnect_loop

        def spy():
            loop_started.set()

        c.start_reconnect_loop = spy
        c.connect()
        assert loop_started.is_set()


# ---------------------------------------------------------------------------
# Reconnect backoff schedule
# ---------------------------------------------------------------------------


class TestReconnectBackoff:
    def test_backoff_schedule_cycles_correctly(self):
        """_reconnect_loop sleeps with [1, 5, 30, 1, 5, ...] on repeated failures."""
        c = _client(backoff_schedule=[1, 5, 30])
        c._running = True
        c._connected = False

        calls_made: list[float] = []
        stop_after = 5  # capture 5 sleep calls then stop

        def fake_connect(host, port):
            raise ConnectionRefusedError("down")

        def fake_sleep(delay):
            calls_made.append(delay)
            if len(calls_made) >= stop_after:
                c._running = False

        c._client = MagicMock()
        c._client.connect.side_effect = fake_connect

        with patch("poc.v4_mission_control.infra.mqtt_client.time.sleep", side_effect=fake_sleep):
            c._reconnect_loop()

        # Expected: [1, 5, 30, 1, 5]
        assert calls_made == [1, 5, 30, 1, 5]

    def test_reconnect_loop_stops_when_running_false(self):
        c = _client(backoff_schedule=[0.001])
        c._running = False

        called = []
        with patch("poc.v4_mission_control.infra.mqtt_client.time.sleep",
                   side_effect=lambda d: called.append(d)):
            c._reconnect_loop()

        assert called == []

    def test_reconnect_loop_stops_when_connected(self):
        c = _client(backoff_schedule=[0.001])
        c._running = True
        c._connected = True  # already connected

        called = []
        with patch("poc.v4_mission_control.infra.mqtt_client.time.sleep",
                   side_effect=lambda d: called.append(d)):
            c._reconnect_loop()

        assert called == []

    def test_default_backoff_schedule(self):
        assert DEFAULT_BACKOFF_SCHEDULE == [1.0, 5.0, 30.0]


# ---------------------------------------------------------------------------
# on_connect / on_disconnect callbacks
# ---------------------------------------------------------------------------


class TestCallbacks:
    def test_on_connect_callback_fired(self):
        fired = []
        c = _client(on_connect=lambda: fired.append(True))
        c._paho_on_connect(None, None, None, 0, None)
        assert fired == [True]

    def test_on_disconnect_callback_fired(self):
        fired = []
        c = _client(on_disconnect=lambda: fired.append(True))
        c._connected = True  # start as connected so disconnect fires
        c.start_reconnect_loop = MagicMock()  # prevent thread spin
        c._paho_on_disconnect(None, None, None, 0, None)
        assert fired == [True]

    def test_on_disconnect_not_fired_if_already_disconnected(self):
        fired = []
        c = _client(on_disconnect=lambda: fired.append(True))
        c._connected = False  # was never connected
        c.start_reconnect_loop = MagicMock()
        c._paho_on_disconnect(None, None, None, 0, None)
        assert fired == []

    def test_on_disconnect_starts_reconnect(self):
        c = _client()
        c._connected = True
        c.start_reconnect_loop = MagicMock()
        c._paho_on_disconnect(None, None, None, 0, None)
        c.start_reconnect_loop.assert_called_once()


# ---------------------------------------------------------------------------
# ServiceStatusService cable-test
# ---------------------------------------------------------------------------


class TestServiceStatusCable:
    """Verify MqttReconnectClient callbacks wire into ServiceStatusService."""

    def test_on_connect_calls_report_mqtt_connected(self):
        svc = ServiceStatusService()
        c = _client(on_connect=svc.report_mqtt_connected,
                    on_disconnect=svc.report_mqtt_disconnected)

        # Simulate paho firing on_connect
        c._paho_on_connect(None, None, None, 0, None)
        assert svc.mqtt_connected is True

    def test_on_disconnect_calls_report_mqtt_disconnected(self):
        svc = ServiceStatusService()
        c = _client(on_connect=svc.report_mqtt_connected,
                    on_disconnect=svc.report_mqtt_disconnected)

        c._connected = True
        c.start_reconnect_loop = MagicMock()
        c._paho_on_disconnect(None, None, None, 0, None)
        assert svc.mqtt_connected is False


# ---------------------------------------------------------------------------
# ServiceStatusService standalone tests
# ---------------------------------------------------------------------------


class TestServiceStatusService:
    def test_initial_state(self):
        svc = ServiceStatusService()
        assert svc.mqtt_connected is False
        assert svc.inventory_available is True

    def test_report_mqtt_connected(self):
        svc = ServiceStatusService()
        svc.report_mqtt_connected()
        assert svc.mqtt_connected is True

    def test_report_mqtt_disconnected(self):
        svc = ServiceStatusService()
        svc.report_mqtt_connected()
        svc.report_mqtt_disconnected()
        assert svc.mqtt_connected is False

    def test_report_inventory_failure(self):
        svc = ServiceStatusService()
        svc.report_inventory_failure()
        assert svc.inventory_available is False

    def test_report_inventory_success_recovers(self):
        svc = ServiceStatusService()
        svc.report_inventory_failure()
        svc.report_inventory_success()
        assert svc.inventory_available is True

    def test_as_dict(self):
        svc = ServiceStatusService()
        svc.report_mqtt_connected()
        d = svc.as_dict()
        assert d == {"mqtt": True, "inventory": True}

    def test_ws_broadcast_called_on_change(self):
        ws = MagicMock()
        svc = ServiceStatusService(ws_manager=ws)
        svc.report_mqtt_connected()
        ws.broadcast_sync.assert_called_once()
        args = ws.broadcast_sync.call_args
        assert args[0][0] == "service_status"
        assert args[0][1]["mqtt"] is True

    def test_ws_broadcast_not_called_on_no_change(self):
        ws = MagicMock()
        svc = ServiceStatusService(ws_manager=ws)
        svc.report_mqtt_connected()
        ws.reset_mock()
        svc.report_mqtt_connected()  # same value — no broadcast
        ws.broadcast_sync.assert_not_called()
