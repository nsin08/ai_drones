"""Service connectivity status tracker — W15 G11.

Tracks whether the MQTT broker and the Inventory service are reachable.
On every state change it broadcasts a ``service_status`` WebSocket event so
connected UI clients can update their status badges immediately.

Event payload shape (matches AppShell expectation)::

    {
        "mqtt": true,
        "inventory": true
    }

Usage (wired through ServiceContainer)::

    # From MqttReconnectClient callbacks:
    client = MqttReconnectClient(
        host, port,
        on_connect=runtime.service_status.report_mqtt_connected,
        on_disconnect=runtime.service_status.report_mqtt_disconnected,
    )

    # From an Inventory HTTP call:
    try:
        result = inventory_cb.call(requests.get, url)
        runtime.service_status.report_inventory_success()
    except CircuitOpenError:
        pass   # already marked unavailable
    except Exception:
        runtime.service_status.report_inventory_failure()
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from ..schemas.socket_events import SERVICE_STATUS_EVENT

if TYPE_CHECKING:
    from ..ws.manager import WebSocketManager


class ServiceStatusService:
    """Thread-safe tracker for MQTT + Inventory connectivity.

    Call :meth:`report_mqtt_connected` / :meth:`report_mqtt_disconnected` from
    MQTT client callbacks.  Call :meth:`report_inventory_success` /
    :meth:`report_inventory_failure` from the Inventory circuit breaker.

    Only broadcasts on *actual* state changes to avoid WS spam.
    """

    def __init__(self, ws_manager: WebSocketManager | None = None) -> None:
        self._ws = ws_manager
        self._mqtt_connected: bool = False
        self._inventory_available: bool = True
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def mqtt_connected(self) -> bool:
        with self._lock:
            return self._mqtt_connected

    @property
    def inventory_available(self) -> bool:
        with self._lock:
            return self._inventory_available

    def as_dict(self) -> dict:
        """Return the current status as a dict (suitable for API responses)."""
        with self._lock:
            return {
                "mqtt": self._mqtt_connected,
                "inventory": self._inventory_available,
            }

    # ------------------------------------------------------------------
    # State reporters
    # ------------------------------------------------------------------

    def report_mqtt_connected(self) -> None:
        """Call when the MQTT broker connection is established."""
        self._update("_mqtt_connected", True)

    def report_mqtt_disconnected(self) -> None:
        """Call when the MQTT broker connection drops."""
        self._update("_mqtt_connected", False)

    def report_inventory_success(self) -> None:
        """Call after a successful Inventory HTTP response."""
        self._update("_inventory_available", True)

    def report_inventory_failure(self) -> None:
        """Call after an Inventory HTTP failure or when the circuit opens."""
        self._update("_inventory_available", False)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _update(self, attr: str, value: bool) -> None:
        changed = False
        with self._lock:
            if getattr(self, attr) != value:
                setattr(self, attr, value)
                changed = True

        if changed:
            self._broadcast()

    def _broadcast(self) -> None:
        if self._ws is None:
            return
        self._ws.broadcast_sync(SERVICE_STATUS_EVENT, self.as_dict())
